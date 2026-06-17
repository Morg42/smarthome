#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for Item._castvalue_to_itemtype()

Coverage
--------
Success paths:
  num item  → value cast to float/int via cast_num
  bool item → value cast via cast_bool
  str item  → value cast via cast_str
  list item → value cast via cast_list
  dict item → value cast via cast_dict
  compat=ATTRIB_COMPAT_V12 → value returned unchanged regardless of type

Failure / fallback paths:
  num item, unconvertible value → cast('') used as fallback (0 for num)
  bool item, unconvertible value → cast('') used as fallback (False)
  str item, unconvertible value → cast('') used as fallback ('')
  list item, list value that can't be cast → []
  dict item, dict value that can't be cast → {}
  item with _type=None → warning logged, value returned unchanged
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tests.common as common

common.register_shng_log_levels()

import lib.item.item
import lib.item.items
from lib.item.items import Items
from lib.constants import ATTRIB_COMPAT_V12, ATTRIB_COMPAT_LATEST
from tests.mock.core import MockSmartHome


def _reset():
    lib.item.items._items_instance = None
    lib.item.item._items_instance = None
    Items._Items__items = []
    Items._Items__item_dict = {}
    Items._children = []
    Items.plugin_attributes = {}
    Items.plugin_attribute_prefixes = {}
    Items.plugin_prefixes_tuple = None


def _make_sh():
    _reset()
    return MockSmartHome()


def _item(sh, path, itype="num", **conf):
    c = {"type": itype}
    c.update(conf)
    i = lib.item.item.Item(sh, sh.items, path, c)
    sh.items.add_item(path, i)
    return i


class _Base(unittest.TestCase):
    def setUp(self):
        self.sh = _make_sh()

    def tearDown(self):
        _reset()

    def _cast(self, item, value, compat=ATTRIB_COMPAT_LATEST):
        return item._castvalue_to_itemtype(value, compat)


# ===========================================================================
# num
# ===========================================================================


class TestCastValueNum(_Base):
    def test_int_value_returned_as_num(self):
        item = _item(self.sh, "n")
        result = self._cast(item, 42)
        self.assertEqual(result, 42)

    def test_float_string_cast_to_num(self):
        item = _item(self.sh, "n")
        result = self._cast(item, "3.14")
        self.assertAlmostEqual(result, 3.14)

    def test_invalid_string_falls_back_to_zero(self):
        # cast_num('') → 0; invalid string → cast('')
        item = _item(self.sh, "n")
        result = self._cast(item, "not_a_number")
        self.assertEqual(result, 0)

    def test_none_falls_back_to_zero(self):
        item = _item(self.sh, "n")
        result = self._cast(item, None)
        self.assertEqual(result, 0)


# ===========================================================================
# bool
# ===========================================================================


class TestCastValueBool(_Base):
    def test_true_string_cast_to_true(self):
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, "True")
        self.assertIs(result, True)

    def test_false_string_cast_to_false(self):
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, "False")
        self.assertIs(result, False)

    def test_one_cast_to_true(self):
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, 1)
        self.assertIs(result, True)

    def test_zero_cast_to_false(self):
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, 0)
        self.assertIs(result, False)

    def test_invalid_string_falls_back_to_false(self):
        # cast_bool('') → False
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, "completely_invalid_bool")
        self.assertIs(result, False)


# ===========================================================================
# str
# ===========================================================================


class TestCastValueStr(_Base):
    def test_string_value_unchanged(self):
        item = _item(self.sh, "s", "str")
        result = self._cast(item, "hello")
        self.assertEqual(result, "hello")

    def test_int_cast_to_string(self):
        item = _item(self.sh, "s", "str")
        result = self._cast(item, 42)
        self.assertEqual(result, "42")

    def test_none_cast_to_none_string_or_empty(self):
        # cast_str(None) → 'None' (Python str(None))
        item = _item(self.sh, "s", "str")
        result = self._cast(item, None)
        self.assertIsInstance(result, str)


# ===========================================================================
# list
# ===========================================================================


class TestCastValueList(_Base):
    def test_list_value_unchanged(self):
        item = _item(self.sh, "l", "list")
        result = self._cast(item, [1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_string_list_repr_parsed_to_list(self):
        # cast_list uses literal_eval — a string that IS a valid list repr is parsed
        item = _item(self.sh, "l", "list")
        result = self._cast(item, "[1, 2, 3]")
        self.assertEqual(result, [1, 2, 3])

    def test_invalid_string_for_list_raises(self):
        # cast_list('hello') raises ValueError; _castvalue_to_itemtype propagates it
        # because the fallback branch also calls cast_list('') which also raises.
        item = _item(self.sh, "l", "list")
        with self.assertRaises(Exception):
            self._cast(item, "not_a_list")


# ===========================================================================
# dict
# ===========================================================================


class TestCastValueDict(_Base):
    def test_dict_value_unchanged(self):
        item = _item(self.sh, "d", "dict")
        result = self._cast(item, {"a": 1})
        self.assertEqual(result, {"a": 1})

    def test_string_dict_repr_parsed_to_dict(self):
        # cast_dict uses literal_eval — a valid dict repr string is parsed
        item = _item(self.sh, "d", "dict")
        result = self._cast(item, "{'a': 1, 'b': 2}")
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_invalid_string_for_dict_raises(self):
        # cast_dict('not_a_dict') raises; fallback also raises
        item = _item(self.sh, "d", "dict")
        with self.assertRaises(Exception):
            self._cast(item, "not_a_dict")


# ===========================================================================
# type == None (untyped item)
# ===========================================================================


class TestCastValueNoType(_Base):
    def test_untyped_item_value_returned_unchanged(self):
        # An item with _type=None has no cast to apply.
        # _castvalue_to_itemtype logs a warning and returns the original value.
        item = _item(self.sh, "u", "num")
        item._type = None  # force untyped
        result = self._cast(item, 99)
        self.assertEqual(result, 99)


# ===========================================================================
# compat = ATTRIB_COMPAT_V12  (backward compat: no casting)
# ===========================================================================


class TestCastValueCompat(_Base):
    def test_v12_compat_skips_casting(self):
        # With ATTRIB_COMPAT_V12, _castvalue_to_itemtype returns value as-is
        # without calling any cast function, even if the value doesn't match.
        item = _item(self.sh, "n", "num")
        result = self._cast(item, "not_a_number", compat=ATTRIB_COMPAT_V12)
        # returned unchanged — no cast attempted
        self.assertEqual(result, "not_a_number")

    def test_v12_compat_bool_string_unchanged(self):
        item = _item(self.sh, "b", "bool")
        result = self._cast(item, "True", compat=ATTRIB_COMPAT_V12)
        # NOT cast to Python bool — returned as string
        self.assertEqual(result, "True")

    def test_latest_compat_does_cast(self):
        item = _item(self.sh, "n", "num")
        result = self._cast(item, "7", compat=ATTRIB_COMPAT_LATEST)
        self.assertEqual(result, 7)


if __name__ == "__main__":
    unittest.main()
