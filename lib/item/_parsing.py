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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

"""
lib/item/_parsing.py
====================

Attribute-parsing helpers extracted from lib/item/item.py.

Functions
---------
parse_eval_attribute(item, attribute_name, value)
parse_eval_trigger_list_attribute(item, attribute_name, value)
parse_hysteresis_input_attribute(item, attribute_name, value)
parse_hysteresis_xx_threshold_attribute(item, attr, value)
parse_on_xx_list_attribute(item, attr, value)
parse_cycle_attribute(item, attr, value, compat_default)
parse_autotimer_attribute(item, attr, value, compat_default)
build_trigger_condition_eval(item, trigger_condition)

All path-resolution calls go through the existing public/delegate API
on ``Item`` (``get_absolutepath``, ``get_stringwithabsolutepathes``,
``_split_destitem_from_value``) so no additional proxies are needed.

The ``compat_default`` parameter of ``parse_cycle_attribute`` and
``parse_autotimer_attribute`` is supplied by the ``item.py`` delegate,
which reads the module-level ``ATTRIB_COMPAT_DEFAULT`` global.  Passing
it as an argument avoids a circular import.  The returned ``compat``
value from ``split_duration_value_string`` is intentionally discarded by
these two functions (it is not used further in parsing).
"""

import logging

from lib.constants import (
    ATTRIBUTE_SEPARATOR,
    KEY_HYSTERESIS_UPPER_THRESHOLD,
    KEY_HYSTERESIS_LOWER_THRESHOLD,
    KEY_ON_CHANGE,
    KEY_CONDITION,
)

from .helpers import split_duration_value_string

logger = logging.getLogger('lib.item')


# ---------------------------------------------------------------------------
# Eval attribute
# ---------------------------------------------------------------------------

def parse_eval_attribute(item, attribute_name, value):
    """
    Parse and store the ``eval`` attribute on *item*.

    If *value* is an empty string the eval expression is cleared.
    Otherwise relative ``sh.`` paths are expanded to absolute item paths.

    :param item:           ``Item`` instance.
    :param attribute_name: Attribute key (used for logging in path resolution).
    :param value:          Raw attribute value from item configuration.
    """
    if value == '':
        item._eval_unexpanded = ''
        item._eval = None
    else:
        item._eval_unexpanded = value
        value = item.get_stringwithabsolutepathes(value, 'sh.', '(', attribute_name)
        item._eval = value


# ---------------------------------------------------------------------------
# Eval trigger list attribute
# ---------------------------------------------------------------------------

def parse_eval_trigger_list_attribute(item, attribute_name, value):
    """
    Parse and store the ``eval_trigger`` attribute on *item*.

    A bare string is wrapped in a list; each path is expanded from
    relative to absolute.

    :param item:           ``Item`` instance.
    :param attribute_name: Attribute key.
    :param value:          Raw attribute value (string or list of strings).
    """
    if isinstance(value, str):
        value = [value]
    item._trigger_unexpanded = value
    expanded = []
    for path in value:
        expanded.append(item.get_absolutepath(path, attribute_name))
    item._trigger = expanded


# ---------------------------------------------------------------------------
# Hysteresis input attribute
# ---------------------------------------------------------------------------

def parse_hysteresis_input_attribute(item, attribute_name, value):
    """
    Parse and store the ``hysteresis_input`` attribute on *item*.

    The value (an item path, possibly relative) is expanded to an
    absolute path.

    :param item:           ``Item`` instance.
    :param attribute_name: Attribute key.
    :param value:          Raw attribute value.
    """
    item._hysteresis_input_unexpanded = value
    item._hysteresis_input = item.get_absolutepath(value, attribute_name)


# ---------------------------------------------------------------------------
# Hysteresis upper / lower threshold attribute
# ---------------------------------------------------------------------------

def parse_hysteresis_xx_threshold_attribute(item, attr, value):
    """
    Parse and store the upper or lower hysteresis threshold attribute.

    The *value* may optionally contain a timer separated by
    ``ATTRIBUTE_SEPARATOR``.  Both the threshold expression and the
    optional timer expression are expanded for relative ``sh.`` paths.

    :param item:  ``Item`` instance.
    :param attr:  Either ``KEY_HYSTERESIS_UPPER_THRESHOLD`` or
                  ``KEY_HYSTERESIS_LOWER_THRESHOLD``.
    :param value: Raw attribute value.
    """
    if value.find(ATTRIBUTE_SEPARATOR) == -1:
        threshold = item.get_stringwithabsolutepathes(value, 'sh.', '(', attr)
        timer = None
    else:
        threshold_unex, __, timer_unex = value.rpartition(ATTRIBUTE_SEPARATOR)
        threshold = item.get_stringwithabsolutepathes(threshold_unex.strip(), 'sh.', '(', attr)
        timer = item.get_stringwithabsolutepathes(timer_unex.strip(), 'sh.', '(', attr)

    if attr == KEY_HYSTERESIS_UPPER_THRESHOLD:
        item._hysteresis_upper_threshold = threshold
        item._hysteresis_upper_timer = timer
    elif attr == KEY_HYSTERESIS_LOWER_THRESHOLD:
        item._hysteresis_lower_threshold = threshold
        item._hysteresis_lower_timer = timer


# ---------------------------------------------------------------------------
# on_change / on_update list attribute
# ---------------------------------------------------------------------------

def parse_on_xx_list_attribute(item, attr, value):
    """
    Parse and store an ``on_change`` or ``on_update`` attribute.

    Each entry is optionally prefixed by a destination item path
    (``dest_item = eval_expression`` syntax).  Both paths and expressions
    are expanded from relative to absolute.

    :param item:  ``Item`` instance.
    :param attr:  Attribute name (``'on_change'`` or ``'on_update'``).
    :param value: Raw attribute value (string or list of strings).
    """
    if isinstance(value, str):
        value = [value]
    val_list = []
    val_list_unexpanded = []
    dest_var_list = []
    dest_var_list_unexp = []

    for val in value:
        # Separate destination item (if present: ``dest = expr`` syntax).
        dest_item, val = item._split_destitem_from_value(val)
        dest_item = dest_item.strip()
        if dest_item.startswith('sh.'):
            dest_item = dest_item[3:]
        dest_var_list_unexp.append(dest_item.strip())

        # Expand relative destination path.
        dest_item = item.get_absolutepath(dest_item.strip()).strip()

        val_list_unexpanded.append(val)
        val = item.get_stringwithabsolutepathes(val, 'sh.', '(', KEY_ON_CHANGE)
        val_list.append(val)
        dest_var_list.append(dest_item)

    setattr(item, '_' + attr + '_unexpanded', val_list_unexpanded)
    setattr(item, '_' + attr, val_list)
    setattr(item, '_' + attr + '_dest_var', dest_var_list)
    setattr(item, '_' + attr + '_dest_var_unexp', dest_var_list_unexp)


# ---------------------------------------------------------------------------
# Cycle attribute
# ---------------------------------------------------------------------------

def parse_cycle_attribute(item, attr, value, compat_default=''):
    """
    Parse and store the ``cycle`` attribute on *item*.

    The raw *value* is split into a time component and an optional value
    component; both are expanded for relative ``sh.`` references and
    stored as ``item._cycle_time`` / ``item._cycle_value``.

    The *compat_default* is forwarded to ``split_duration_value_string``
    and the returned ``compat`` token is discarded — it is not used in
    parsing.

    :param item:          ``Item`` instance.
    :param attr:          Attribute key (used for path resolution logs).
    :param value:         Raw attribute string.
    :param compat_default: Current ``ATTRIB_COMPAT_DEFAULT`` from ``item.py``
                           (passed by the delegate to avoid circular import).
    """
    cycle_time, cycle_value, _compat = split_duration_value_string(value, compat_default)
    item._cycle_time = item.get_stringwithabsolutepathes(cycle_time, 'sh.', '(', attr)
    item._cycle_value = item.get_stringwithabsolutepathes(cycle_value, 'sh.', '(', attr)


# ---------------------------------------------------------------------------
# Autotimer attribute
# ---------------------------------------------------------------------------

def parse_autotimer_attribute(item, attr, value, compat_default=''):
    """
    Parse and store the ``autotimer`` attribute on *item*.

    Analogous to :func:`parse_cycle_attribute` but populates
    ``item._autotimer_time`` / ``item._autotimer_value``.

    :param item:          ``Item`` instance.
    :param attr:          Attribute key.
    :param value:         Raw attribute string.
    :param compat_default: Current ``ATTRIB_COMPAT_DEFAULT`` from ``item.py``.
    """
    auto_time, auto_value, _compat = split_duration_value_string(value, compat_default)
    item._autotimer_time = item.get_stringwithabsolutepathes(auto_time, 'sh.', '(', attr)
    item._autotimer_value = item.get_stringwithabsolutepathes(auto_value, 'sh.', '(', attr)


# ---------------------------------------------------------------------------
# Trigger condition eval builder
# ---------------------------------------------------------------------------

def build_trigger_condition_eval(item, trigger_condition):
    """
    Build a Python boolean expression from the ``trigger_condition``
    attribute list.

    Each entry in *trigger_condition* is an OR-clause dict whose values
    are lists of AND conditions.  The function:

    * skips the special ``'value'`` key (handled elsewhere at eval time),
    * rewrites bare ``=`` to ``==`` (but not ``==``, ``<=``, ``>=``,
      ``=>``, ``=<``),
    * normalises ``true``/``false`` (case-insensitive) to Python
      ``True``/``False``,
    * expands relative ``sh.`` item references to absolute paths,
    * joins AND conditions with ``') and ('`` and OR clauses with
      ``') or ('``.

    :param item:              ``Item`` instance.
    :param trigger_condition: List of OR-clause dicts from item config.
    :return:                  Python boolean expression string.
    :rtype:                   str
    """
    wrk_eval = []
    for or_cond in trigger_condition:
        for ckey in or_cond:
            if ckey.lower() == 'value':
                # 'value' is handled separately at eval time — skip.
                pass
            else:
                and_cond = []
                for cond in or_cond[ckey]:
                    wrk = cond

                    # Rewrite bare ``=`` to ``==``, but guard compound
                    # operators (``==``, ``<=``, ``>=``, ``=>``, ``=<``).
                    if (wrk.find('=') != -1) and (wrk.find('==') == -1) and \
                            (wrk.find('<=') == -1) and (wrk.find('>=') == -1) and \
                            (wrk.find('=<') == -1) and (wrk.find('=>') == -1):
                        wrk = wrk.replace('=', '==')

                    # Normalise ``true`` / ``false`` → Python booleans.
                    p = wrk.lower().find('true')
                    if p != -1:
                        wrk = wrk[:p] + 'True' + wrk[p + 4:]
                    p = wrk.lower().find('false')
                    if p != -1:
                        wrk = wrk[:p] + 'False' + wrk[p + 5:]

                    # Expand relative item paths.
                    wrk = item.get_stringwithabsolutepathes(wrk, 'sh.', '(', KEY_CONDITION)

                    and_cond.append(wrk)

                wrk = ') and ('.join(and_cond)
                if len(or_cond[ckey]) > 1:
                    wrk = '(' + wrk + ')'
                wrk_eval.append(wrk)

                result = ') or ('.join(wrk_eval)

    if len(trigger_condition) > 1:
        result = '(' + result + ')'

    return result
