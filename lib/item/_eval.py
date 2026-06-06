#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-2025   Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

"""
Eval / on_change / on_update execution for Item.

Extracted from lib/item/item.py.

Entry points
------------
run_eval(item, value, caller, source, dest)
    Called when an item's eval expression must be evaluated.
    Replaces Item.__run_eval().

run_on_xxx(item, path, value, on_dest, on_eval, attr, caller, source, dest)
    Common runner for on_update and on_change entries.
    Replaces Item._run_on_xxx().

run_on_update(item, value, caller, source, dest)
    Runs all on_update entries for the item.
    Replaces Item.__run_on_update().

run_on_change(item, value, caller, source, dest)
    Runs all on_change entries for the item.
    Replaces Item.__run_on_change().

All functions access only single-underscore attributes and public methods on
the Item to avoid Python name-mangling problems.  The one exception is calling
item._update_item() — a thin public proxy that Item exposes for this purpose
(it delegates to the private Item.__update()).
"""

import logging
import lib.env

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# run_eval  (replaces Item.__run_eval)
# ---------------------------------------------------------------------------

def run_eval(item, value=None, caller='Eval', source=None, dest=None):
    """
    Evaluate the item's ``eval`` expression.

    Called from Item.__run_eval() which is passed to the scheduler as a
    callable.  All scheduler bookkeeping stays in the Item method; this
    function contains only the evaluation logic.
    """
    if caller.lower().startswith('admin:'):
        caller = caller[6:] + ':admin'
    if (not caller.lower().startswith('eval:')) and (not caller.lower().endswith(':eval')):
        caller = 'Eval:' + caller

    if item._sh.shng_status['code'] < 14:
        logger.dbghigh(
            f"Item {item._path}: Running __run_eval before initialization is finished"
            f" - eval run ignored- caller={caller}, source={source}"
            f"  -  shng_status{item._sh.shng_status}"
        )
        return
    if item._sh.shng_status['code'] < 20 and not caller.startswith('Init'):
        logger.info(
            f"Item {item._path}: Running __run_eval before initialization is finished"
            f" - caller={caller}, source={source}, value={value}"
            f"  -  shng_status{item._sh.shng_status}"
        )
    if item._sh.shng_status['code'] > 20:
        logger.info(
            f"Item {item._path}: Running __run_eval after leaving run-mode"
            f" - caller={caller}, source={source}, value={value}"
            f"  -  shng_status{item._sh.shng_status}"
        )

    if not item._eval:
        return

    # Test if a conditional trigger is defined
    if item._trigger_condition is not None:
        try:
            # set up environment for calculating eval-expression
            sh     = item._sh         # noqa: F841
            shtime = item.shtime      # noqa: F841

            from lib.item.items import Items
            items = Items.get_instance()  # noqa: F841

            import math               # noqa: F401, F841
            import lib.userfunctions as uf  # noqa: F401, F841
            env    = lib.env          # noqa: F841

            cond = eval(item._trigger_condition)
            logger.warning(
                f"Item '{item._path}': Condition result '{cond}'"
                f" evaluating trigger condition {item._trigger_condition}"
            )
        except Exception as e:
            log_msg = (
                f"Item '{item._path}': Problem evaluating trigger condition"
                f" '{item._trigger_condition}': {e}"
            )
            if item._sh.shng_status['code'] != 20 and caller != 'Init':
                logger.debug(log_msg)
            else:
                logger.warning(log_msg)
            return
    else:
        cond = True

    if cond is not True:
        return

    # set up environment for calculating eval-expression
    sh     = item._sh          # noqa: F841
    shtime = item.shtime       # noqa: F841

    from lib.item.items import Items
    items = Items.get_instance()  # noqa: F841

    import math                # noqa: F401, F841
    import lib.userfunctions as uf  # noqa: F401, F841
    env    = lib.env           # noqa: F841

    try:
        item._history.record_trigger(caller, source, item.shtime)

        try:
            triggered = source in item._trigger
        except Exception:
            triggered = False

        if item._eval_on_trigger_only and not triggered:
            logger.info(
                f'Item {item._path} Eval triggered by:'
                f' {item._history.get_last_trigger_by()},'
                f' not in eval_triggers, but eval_on_trigger_only set.'
                f' Ignoring eval expression, setting value "{value}"'
            )
        else:
            logger.debug(
                f"Item {item._path} Eval triggered by:"
                f" {item._history.get_last_trigger_by()},"
                f" Evaluating item with value {value}."
                f" Eval expression: {item._eval}"
            )

            # if crontab: init = x is set, x is transferred as a string;
            # re-try eval with x converted to float for that case
            try:
                value = eval(item._eval)
            except Exception:
                value = item.cast(value)
                value = eval(item._eval)

    except Exception as e:
        # Adding "None" as the "destination" information at end of triggered_by
        # helps figure out whether an eval expression was successfully evaluated.
        item._history.record_trigger_none(caller, source)
        if e.__class__.__name__ == 'KeyError':
            log_msg = f"Item '{item._path}': problem evaluating '{item._eval}' - KeyError (in dict)"
        else:
            log_msg = (
                f"Item '{item._path}': problem evaluating '{item._eval}'"
                f" - {e.__class__.__name__}: {e}"
            )
        if item._sh.shng_status['code'] != 20 and caller != 'Init':
            logger.debug(log_msg + " (status_code={}/caller={})".format(item._sh.shng_status['code'], caller))
        else:
            logger.warning(log_msg)
    else:
        if value is None:
            logger.debug(f"Item {item._path}: evaluating {item._eval} returns None")
        else:
            item._update_item(value, caller, source, dest)


# ---------------------------------------------------------------------------
# run_on_xxx  (replaces Item._run_on_xxx)
# ---------------------------------------------------------------------------

def run_on_xxx(item, path, value, on_dest, on_eval, attr='?',
               caller=None, source=None, dest=None):
    """
    Common runner for on_update and on_change entries.

    :param item:    Item instance that owns this on_update/on_change list
    :param path:    item path (same as item._path)
    :param value:   current item value
    :param on_dest: destination item path, or '' for no-dest syntax
    :param on_eval: eval expression string
    :param attr:    descriptive label ('On_Change' or 'On_Update')
    """
    # set up environment for calculating eval-expression
    sh     = item._sh       # noqa: F841
    shtime = item.shtime    # noqa: F841

    from lib.item.items import Items
    _items_instance = Items.get_instance()
    items = _items_instance  # noqa: F841

    import math             # noqa: F401, F841
    import lib.userfunctions as uf  # noqa: F401, F841
    env    = lib.env        # noqa: F841

    logger.info(f"Item '{path}': '{attr}' evaluating {on_dest} = {on_eval}")

    # if syntax without '=' is used, inject caller and source into the call
    if on_dest == '':
        on_eval = on_eval.strip()
        if on_eval.endswith(')'):
            test = on_eval.replace(' ', '')
            if test.lower().find(',caller=') == -1 and test.lower().find(',source=') == -1:
                on_eval = on_eval[:-1] + ", caller='" + attr + "', source='" + path + "')"
            if test.lower().find(',caller=') > -1 and test.lower().find(',source=') == -1:
                on_eval = on_eval[:-1] + ", source='" + path + "')"
            if test.lower().find(',caller=') == -1 and test.lower().find(',source=') > -1:
                on_eval = on_eval[:-1] + ", caller='" + attr + "')"

    # try evaluating the expression (this also assigns value when no-dest syntax is used)
    try:
        dest_value = eval(on_eval)
    except Exception as e:
        logger.warning(
            f"Item {path}: '{attr}' item-value='{value}'"
            f" problem evaluating {on_eval}: {e}"
        )
    else:
        if dest_value is not None:
            if on_dest != '':
                dest_item = _items_instance.return_item(on_dest)
                if dest_item is not None:
                    dest_item._update_item(dest_value, caller=attr, source=path)
                    logger.debug(
                        f" - : '{attr}' finally evaluating {on_dest} = {on_eval},"
                        f" result={dest_value}"
                    )
                else:
                    logger.error(
                        f"Item {path}: '{attr}' has not found dest_item '{on_dest}'"
                        f" = {on_eval}, result={dest_value}"
                    )
            else:
                _ = eval(on_eval)
                logger.debug(f" - : '{attr}' finally evaluating {on_eval}, result={dest_value}")
        else:
            logger.debug(f" - : '{attr}' {on_dest} not set (cause: eval=None)")


# ---------------------------------------------------------------------------
# run_on_update  (replaces Item.__run_on_update)
# ---------------------------------------------------------------------------

def run_on_update(item, value=None, caller=None, source=None, dest=None):
    """Evaluate all on_update entries for *item*."""
    if item._on_update:
        for on_update_dest, on_update_eval in zip(item._on_update_dest_var, item._on_update):
            run_on_xxx(item, item._path, value, on_update_dest, on_update_eval,
                       'On_Update', caller=caller, source=source, dest=dest)


# ---------------------------------------------------------------------------
# run_on_change  (replaces Item.__run_on_change)
# ---------------------------------------------------------------------------

def run_on_change(item, value=None, caller=None, source=None, dest=None):
    """Evaluate all on_change entries for *item*."""
    if item._on_change:
        for on_change_dest, on_change_eval in zip(item._on_change_dest_var, item._on_change):
            run_on_xxx(item, item._path, value, on_change_dest, on_change_eval,
                       'On_Change', caller=caller, source=source, dest=dest)
