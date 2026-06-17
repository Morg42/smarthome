#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for Item history tracking (lib/item/item.py)

Planned extraction target: lib/item/_history.py

The central invariant under test:
  - item(same_value)  → last_update advances,  last_change does NOT
  - item(new_value)   → both last_update and last_change advance
  - enforce_change=True → same-value write also advances last_change

Coverage
--------
_set_value / __update paths:
  update-without-change    last_update advances, last_change frozen
  update-with-change       both advance
  enforce_change=True      same value treated as change
  enforce_updates=True     plugin callbacks fire on same-value write

Caller / source attribution:
  changed_by, updated_by, triggered_by public methods
  prev_change_by, prev_update_by after two writes

Public history methods (backward-compat API on Item):
  last_change(), age(), last_update(), update_age()
  prev_change(), prev_age(), prev_value(), prev_update()
  last_change() frozen on same-value write

last_value / prev_value sequencing:
  three-step sequence to distinguish __last_value from __prev_value
"""

import datetime
import logging
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tests.common as common

common.register_shng_log_levels()

import lib.item.item
import lib.item.items
from lib.item.items import Items
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


def _item(sh, path="test", itype="num", **conf):
    c = {"type": itype}
    c.update(conf)
    i = lib.item.item.Item(sh, sh, path, c)
    sh.items.add_item(path, i)
    return i


class _Base(unittest.TestCase):
    def setUp(self):
        self.sh = _make_sh()

    def tearDown(self):
        _reset()


# ===========================================================================
# The core invariant: update-without-change
# ===========================================================================


class TestUpdateWithoutChange(_Base):
    """
    When the same value is written twice, last_update advances but last_change
    does NOT.  This is the primary invariant that _history.py must preserve.
    """

    def test_same_value_advances_last_update(self):
        item = _item(self.sh)
        item(5)
        t0 = item.property.last_update
        time.sleep(0.05)
        item(5)
        self.assertGreater(item.property.last_update, t0)

    def test_same_value_does_not_advance_last_change(self):
        item = _item(self.sh)
        item(5)
        t_change = item.property.last_change
        time.sleep(0.05)
        item(5)
        self.assertEqual(item.property.last_change, t_change)

    def test_different_value_advances_last_change(self):
        item = _item(self.sh)
        item(5)
        t0 = item.property.last_change
        time.sleep(0.05)
        item(6)
        self.assertGreater(item.property.last_change, t0)

    def test_different_value_advances_last_update(self):
        item = _item(self.sh)
        item(5)
        t0 = item.property.last_update
        time.sleep(0.05)
        item(6)
        self.assertGreater(item.property.last_update, t0)

    def test_same_value_advances_prev_update(self):
        item = _item(self.sh)
        item(5)
        time.sleep(0.05)
        item(5)
        # prev_update should now hold what last_update was before the same-value write
        self.assertLessEqual(item.property.prev_update, item.property.last_update)

    def test_same_value_does_not_advance_prev_change(self):
        item = _item(self.sh)
        item(5)
        pc = item.property.prev_change
        time.sleep(0.05)
        item(5)
        self.assertEqual(item.property.prev_change, pc)

    def test_public_last_change_method_frozen_on_same_value(self):
        item = _item(self.sh)
        item(5)
        t_change = item.last_change()
        time.sleep(0.05)
        item(5)
        self.assertEqual(item.last_change(), t_change)


# ===========================================================================
# enforce_change — same value treated as change
# ===========================================================================


class TestEnforceChange(_Base):
    def test_enforce_change_advances_last_change_on_same_value(self):
        item = _item(self.sh)
        item(5)
        item.property.enforce_change = True
        t0 = item.property.last_change
        time.sleep(0.05)
        item(5)
        self.assertGreater(item.property.last_change, t0)

    def test_enforce_change_advances_prev_change_on_same_value(self):
        item = _item(self.sh)
        item(5)
        item.property.enforce_change = True
        pc_before = item.property.last_change
        time.sleep(0.05)
        item(5)
        self.assertEqual(item.property.prev_change, pc_before)


# ===========================================================================
# enforce_updates — plugin callbacks fire on same-value write
# ===========================================================================


class TestEnforceUpdates(_Base):
    def test_enforce_updates_triggers_method_on_same_value(self):
        item = _item(self.sh)
        item(5)
        item.property.enforce_updates = True
        calls = []
        item.add_method_trigger(lambda i, c, s, d: calls.append(1))
        item(5)  # same value — without enforce_updates this would not fire
        self.assertEqual(len(calls), 1)

    def test_without_enforce_updates_no_callback_on_same_value(self):
        item = _item(self.sh)
        item(5)
        calls = []
        item.add_method_trigger(lambda i, c, s, d: calls.append(1))
        item(5)  # same value — should not fire
        self.assertEqual(len(calls), 0)


# ===========================================================================
# Caller / source attribution
# ===========================================================================


class TestCallerAttribution(_Base):
    def test_changed_by_contains_caller(self):
        item = _item(self.sh)
        item(1, caller="Scheduler")
        self.assertIn("Scheduler", item.changed_by())

    def test_changed_by_contains_source(self):
        item = _item(self.sh)
        item(1, caller="Plugin", source="my_source")
        self.assertIn("my_source", item.changed_by())

    def test_updated_by_tracks_caller(self):
        item = _item(self.sh)
        item(1, caller="TestCaller")
        self.assertIn("TestCaller", item.updated_by())

    def test_updated_by_advances_on_same_value(self):
        item = _item(self.sh)
        item(5, caller="First")
        item(5, caller="Second")
        self.assertIn("Second", item.updated_by())

    def test_triggered_by_tracks_caller(self):
        item = _item(self.sh)
        item(1, caller="TriggerCaller")
        self.assertIn("TriggerCaller", item.triggered_by())

    def test_prev_change_by_holds_previous_caller(self):
        item = _item(self.sh)
        item(1, caller="First")
        item(2, caller="Second")
        self.assertIn("First", item.property.prev_change_by)

    def test_prev_update_by_holds_previous_update_caller(self):
        item = _item(self.sh)
        item(5, caller="First")
        item(5, caller="Second")  # same-value update
        self.assertIn("First", item.property.prev_update_by)


# ===========================================================================
# Public history methods (backward-compat API on Item)
# ===========================================================================


class TestPublicHistoryMethods(_Base):
    def test_last_change_returns_datetime(self):
        item = _item(self.sh)
        self.assertIsInstance(item.last_change(), datetime.datetime)

    def test_last_update_returns_datetime(self):
        item = _item(self.sh)
        self.assertIsInstance(item.last_update(), datetime.datetime)

    def test_age_returns_nonnegative_float(self):
        item = _item(self.sh)
        self.assertGreaterEqual(item.age(), 0)

    def test_update_age_returns_nonnegative_float(self):
        item = _item(self.sh)
        self.assertGreaterEqual(item.update_age(), 0)

    def test_prev_change_returns_datetime(self):
        item = _item(self.sh)
        self.assertIsInstance(item.prev_change(), datetime.datetime)

    def test_prev_age_returns_nonnegative_float(self):
        item = _item(self.sh)
        self.assertGreaterEqual(item.prev_age(), 0)

    def test_prev_value_method_returns_last_value(self):
        # prev_value() delegates to property.last_value (__last_value),
        # i.e. the value immediately before the current one.
        item = _item(self.sh)
        item(10)
        item(20)
        item(30)
        # last_value = 20 (the value just before 30)
        self.assertEqual(item.prev_value(), 20)
        self.assertEqual(item.prev_value(), item.property.last_value)

    def test_prev_update_returns_datetime(self):
        item = _item(self.sh)
        self.assertIsInstance(item.prev_update(), datetime.datetime)

    def test_age_grows_over_time(self):
        item = _item(self.sh)
        item(1)
        a0 = item.age()
        time.sleep(0.1)
        self.assertGreater(item.age(), a0)

    def test_last_change_matches_property(self):
        item = _item(self.sh)
        item(7)
        self.assertEqual(item.last_change(), item.property.last_change)


# ===========================================================================
# last_value / prev_value sequencing
# ===========================================================================


class TestValueSequencing(_Base):
    """
    Three-step sequence distinguishes __last_value from __prev_value.

    Start:  _value=0, __last_value=None, __prev_value=None
    item(10): __prev_value=None,  __last_value=0,  _value=10
    item(20): __prev_value=0,     __last_value=10, _value=20
    item(30): __prev_value=10,    __last_value=20, _value=30
    """

    def test_last_value_is_previous_current(self):
        item = _item(self.sh)
        item(10)
        item(20)
        self.assertEqual(item.property.last_value, 10)

    def test_prev_value_is_two_behind(self):
        item = _item(self.sh)
        item(10)
        item(20)
        item(30)
        self.assertEqual(item.property.prev_value, 10)

    def test_last_value_tracks_each_change(self):
        item = _item(self.sh)
        item(10)
        item(20)
        item(30)
        self.assertEqual(item.property.last_value, 20)

    def test_last_value_initial_is_type_default(self):
        # After one set: __last_value = initial default (0 for num)
        item = _item(self.sh)
        item(10)
        # last_value holds what _value was before this set
        self.assertEqual(item.property.last_value, 0)

    def test_prev_value_is_readonly(self):
        item = _item(self.sh)
        item(10)
        item.property.prev_value = 999
        self.assertNotEqual(item.property.prev_value, 999)

    def test_last_value_is_readonly(self):
        item = _item(self.sh)
        item(10)
        item.property.last_value = 999
        self.assertNotEqual(item.property.last_value, 999)


if __name__ == "__main__":
    unittest.main()
