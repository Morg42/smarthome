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
lib/item/_casting.py
====================

Value-casting helpers extracted from lib/item/item.py.

Functions
---------
castvalue_to_itemtype(item, value, compat)
    Cast *value* to the item's declared type (no-op when compat=v1.2).

cast_duration(item, time, test)
    Convert a human-readable duration string (``'5m'``, ``'2h30s'``, …)
    to an integer number of seconds.

These functions access only single-underscore attributes on *item* and
call ``item.shtime`` so no name-mangling proxies are required.

The ``item.py`` methods ``_castvalue_to_itemtype`` and ``_cast_duration``
are kept as one-line delegates so the public / semi-public API and all
callers (``_autotimer.py``, ``_build_cycledict``, etc.) remain unchanged.
"""

import logging
import sys

from lib.constants import ATTRIB_COMPAT_LATEST

from .helpers import (
    cast_str,
    cast_list,
    cast_dict,
    cast_bool,
    cast_num,
    cast_foo,
    cast_scene,
    cast_timestamp,
    cast_datetime,
)

logger = logging.getLogger('lib.item')

# ---------------------------------------------------------------------------
# Mapping from item-type name to the appropriate cast function.
# Mirrors the original ``globals()['cast_' + self._type]`` pattern while
# being explicit and independent of another module's global namespace.
# ---------------------------------------------------------------------------
_CAST_MAP: dict = {
    'str':       cast_str,
    'list':      cast_list,
    'dict':      cast_dict,
    'bool':      cast_bool,
    'num':       cast_num,
    'foo':       cast_foo,
    'scene':     cast_scene,
    'timestamp': cast_timestamp,
    'datetime':  cast_datetime,
}


# ---------------------------------------------------------------------------
# castvalue_to_itemtype
# ---------------------------------------------------------------------------

def castvalue_to_itemtype(item, value, compat=ATTRIB_COMPAT_LATEST):
    """
    Cast *value* to the type declared for *item*.

    When backward-compatibility mode ``ATTRIB_COMPAT_V12`` is active the
    value is returned unmodified.

    If the cast raises an exception a warning is logged and a safe fallback
    is returned:

    * ``list``  → ``[]``
    * ``dict``  → ``{}``
    * anything else → ``mycast('')``

    :param item:   ``Item`` instance.
    :param value:  Value to cast.
    :param compat: Compatibility flag (default ``ATTRIB_COMPAT_LATEST``).
    :return:       Casted (or original) value.
    """
    if compat == ATTRIB_COMPAT_LATEST:
        if item._type is not None:
            mycast = _CAST_MAP.get(item._type)
            if mycast is None:
                # Unknown type — fall back gracefully.
                logger.warning(f"Item {item._path}: No cast function for type '{item._type}'")
                return value
            try:
                value = mycast(value)
            except Exception:
                logger.warning(
                    f"Item {item._path}: Unable to cast '{str(value)}' to {item._type}"
                )
                if isinstance(value, list):
                    value = []
                elif isinstance(value, dict):
                    value = {}
                else:
                    value = mycast('')
        else:
            logger.warning(
                f"Item {item._path}: Unable to cast '{str(value)}' to {item._type}"
            )
    return value


# ---------------------------------------------------------------------------
# cast_duration
# ---------------------------------------------------------------------------

def cast_duration(item, time, test=False):
    """
    Convert a duration string to an integer number of seconds.

    Supported formats:

    * plain integer or float (``45``, ``3.0``) → seconds
    * string integer (``'45'``)
    * seconds suffix (``'45s'``)
    * minutes suffix (``'5m'``) → 300
    * hours suffix (``'2h'``) → 7200
    * combinations (``'2h5m45s'``)
    * item reference starting with ``sh.`` → returned as-is (scheduler
      resolves it later)

    If *test* is ``True`` no warning is emitted on parse failure; only
    ``False`` is returned.

    :param item: ``Item`` instance (supplies ``shtime`` and ``_path``).
    :param time: Duration to parse.
    :param test: Suppress warning logs when ``True``.
    :return:     Seconds as ``int``, the original ``str`` for ``sh.``
                 references, or ``False`` on failure.
    """
    if isinstance(time, str):
        if time.startswith("sh."):
            # Item reference — pass through; scheduler resolves it.
            return time

        time_in_sec = item.shtime.to_seconds(time, test=True)
        if time_in_sec == -1:
            if not test:
                logger.warning(
                    f"Item {item._path} - _cast_duration: "
                    f"Unable to convert parameter 'time' to seconds (time={time})"
                )
            time_in_sec = False

    elif isinstance(time, int):
        time_in_sec = int(time)
    elif isinstance(time, float):
        time_in_sec = int(time)
    else:
        if not test:
            logger.warning(
                f"Item {item._path} - _cast_duration: "
                f"Unable to convert parameter 'time' to int (time={time})"
            )
        time_in_sec = False

    return time_in_sec


# ---------------------------------------------------------------------------
# run_attribute_eval
# ---------------------------------------------------------------------------

def run_attribute_eval(item, eval_expression, result_type='num', result_error=''):
    """
    Evaluate an expression string used in item attributes such as
    ``autotimer``, ``cycle``, ``hysteresis_upper_threshold``, and
    ``hysteresis_lower_threshold``.

    The eval environment provides: ``sh``, ``shtime``, ``items``, ``math``,
    ``uf`` (lib.userfunctions), ``env`` (lib.env) — matching the environment
    used by the main item eval path.

    On ``NameError`` the undefined name is replaced by a quoted string and
    evaluation is retried.  Any other exception or a non-numeric result when
    ``result_type='num'`` is expected both log an error and return
    *result_error* / ``0`` respectively.

    :param item:            ``Item`` instance.
    :param eval_expression: Expression string to evaluate.
    :param result_type:     ``'num'`` (default) or ``'str'``.
    :param result_error:    Value returned on evaluation error (default ``''``).
    :return:                Evaluated result.
    """
    from lib.item.items import Items
    import lib.env
    import lib.userfunctions as uf  # noqa: F401 (used in eval environment)
    import math                     # noqa: F401 (used in eval environment)

    sh = item._sh                   # noqa: F841 (used in eval environment)
    shtime = item.shtime            # noqa: F841 (used in eval environment)
    items = Items.get_instance()    # noqa: F841 (used in eval environment)
    env = lib.env                   # noqa: F841 (used in eval environment)

    eval_expression = str(eval_expression)
    try:
        result = eval(eval_expression)
    except NameError:
        _, ex, _ = sys.exc_info()
        err = str(ex)
        if err.startswith("name '") and err.endswith("' is not defined"):
            var = err[6:-16]
        eval_expression2 = eval_expression.replace(var, "'" + var + "'")
        try:
            result = eval('"' + eval_expression2 + '"')
        except Exception as e:
            logger.error(
                f"Item '{item._path}': run_attribute_eval({eval_expression2}): "
                f"Problem evaluating '{eval_expression2}' - Exception {e}"
            )
            result = result_error
    except Exception as e:
        logger.error(
            f"Item '{item._path}': run_attribute_eval({eval_expression}): "
            f"Problem evaluating '{eval_expression}' - Exception {e}"
        )
        result = result_error

    if result_type == 'num':
        if not isinstance(result, (int, float)):
            logger.error(
                f"Item '{item._path}': run_attribute_eval({eval_expression}): "
                f"Attribute expression '{eval_expression}' evaluated to a "
                f"non-numeric value '{result}', using 0 instead"
            )
            result = 0

    return result
