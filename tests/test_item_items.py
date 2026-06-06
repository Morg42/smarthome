#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for lib/item/items.py

Strategy
--------
Tests create a fresh Items instance via MockSmartHome, then manipulate
its state directly (add_item / create Item objects) rather than going
through load_itemdefinitions (which needs the full file system layout).
Class-level attributes are reset in setUp to prevent state leaking between
tests.

Coverage
--------
Items class:
  get_instance()
  add_item(), remove_item()
  return_item(), return_items() (ordered and unordered)
  match_items() — plain regex, with attr, with attr+value
  _attribute_find() — all documented cases
  find_items(), find_children()
  item_count(), get_toplevel_items()
  add_plugin_attribute(), add_plugin_attribute_prefix()
  plugin_attribute_exists()
  return_struct_definitions() (delegates to Structs)
"""

import collections
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def _reg_levels():
    for lvl, name in [(31, 'NOTICE'), (13, 'DBGHIGH'), (12, 'DBGMED'), (11, 'DBGLOW'), (9, 'DEVELOP')]:
        if not hasattr(logging.getLoggerClass(), name.lower()):
            def _make(l):
                def _m(self, msg, *a, **kw):
                    if self.isEnabledFor(l): self._log(l, msg, a, **kw)
                return _m
            logging.addLevelName(lvl, name)
            setattr(logging, name, lvl)
            setattr(logging.getLoggerClass(), name.lower(), _make(lvl))
_reg_levels()

import lib.item
import lib.item.item
import lib.item.items
from lib.item.items import Items
from tests.mock.core import MockSmartHome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_items_class():
    """Reset Items class-level state so each test starts fresh.

    lib.item.items and lib.item.item each hold their own _items_instance global.
    Both must be cleared so subsequent test files get a fresh registry.
    """
    lib.item.items._items_instance = None
    lib.item.item._items_instance = None   # separate global in item.py
    Items._Items__items = []
    Items._Items__item_dict = {}
    Items._children = []
    Items.plugin_attributes = {}
    Items.plugin_attribute_prefixes = {}
    Items.plugin_prefixes_tuple = None


def _make_sh():
    _reset_items_class()
    return MockSmartHome()


class _ItemsTestBase(unittest.TestCase):
    """Mixin that resets Items class-level state both before and after each test.

    Items uses class-level __items / __item_dict etc., so if we only reset in
    setUp the dirty state leaks into subsequent test files (e.g. test_plugin.py).
    """

    def setUp(self):
        self.sh = _make_sh()

    def tearDown(self):
        _reset_items_class()


def _make_item(sh, path, itype='foo', **conf_extra):
    conf = {'type': itype}
    conf.update(conf_extra)
    item = lib.item.item.Item(sh, sh, path, conf)
    sh.items.add_item(path, item)
    return item


# ===========================================================================
# get_instance
# ===========================================================================

class TestItemsGetInstance(_ItemsTestBase):

    def test_get_instance_returns_items_object(self):
        self.assertIsInstance(Items.get_instance(), Items)

    def test_get_instance_same_as_sh_items(self):
        self.assertIs(Items.get_instance(), self.sh.items)


# ===========================================================================
# add_item / return_item / item_count
# ===========================================================================

class TestItemsAddReturn(_ItemsTestBase):

    def test_add_and_return_item(self):
        item = _make_item(self.sh, 'floor.light')
        self.assertIs(self.sh.items.return_item('floor.light'), item)

    def test_return_item_missing_returns_none(self):
        self.assertIsNone(self.sh.items.return_item('does.not.exist'))

    def test_item_count_increments(self):
        self.assertEqual(self.sh.items.item_count(), 0)
        _make_item(self.sh, 'a')
        self.assertEqual(self.sh.items.item_count(), 1)
        _make_item(self.sh, 'b')
        self.assertEqual(self.sh.items.item_count(), 2)

    def test_add_item_idempotent_path(self):
        item = _make_item(self.sh, 'x')
        _make_item(self.sh, 'x')       # second add of same path → overwrites dict but not list
        self.assertEqual(self.sh.items.item_count(), 1)

    def test_add_item_updates_dict(self):
        item1 = lib.item.item.Item(self.sh, self.sh, 'dup', {'type': 'num'})
        item2 = lib.item.item.Item(self.sh, self.sh, 'dup', {'type': 'str'})
        self.sh.items.add_item('dup', item1)
        self.sh.items.add_item('dup', item2)
        # latest item wins in dict
        self.assertIs(self.sh.items.return_item('dup'), item2)


# ===========================================================================
# return_items
# ===========================================================================

class TestItemsReturnItems(_ItemsTestBase):

    def setUp(self):
        super().setUp()
        _make_item(self.sh, 'charlie')
        _make_item(self.sh, 'alpha')
        _make_item(self.sh, 'bravo')

    def test_return_items_yields_all(self):
        items = list(self.sh.items.return_items())
        self.assertEqual(len(items), 3)

    def test_return_items_ordered(self):
        paths = [i.property.path for i in self.sh.items.return_items(ordered=True)]
        self.assertEqual(paths, sorted(paths))

    def test_return_items_unordered_insertion_order(self):
        paths = [i.property.path for i in self.sh.items.return_items(ordered=False)]
        self.assertEqual(paths, ['charlie', 'alpha', 'bravo'])


# ===========================================================================
# match_items
# ===========================================================================

class TestItemsMatchItems(_ItemsTestBase):

    def setUp(self):
        super().setUp()
        self.item_a = _make_item(self.sh, 'floor.kitchen.light', 'bool', my_plugin='yes')
        self.item_b = _make_item(self.sh, 'floor.kitchen.temp',  'num',  my_plugin='no')
        self.item_c = _make_item(self.sh, 'floor.bedroom.light', 'bool', my_plugin='yes')

    def test_wildcard_match_all(self):
        result = self.sh.items.match_items('*')
        self.assertEqual(len(result), 3)

    def test_exact_prefix_match(self):
        result = self.sh.items.match_items('floor.kitchen.*')
        paths = {i.property.path for i in result}
        self.assertIn('floor.kitchen.light', paths)
        self.assertIn('floor.kitchen.temp', paths)
        self.assertNotIn('floor.bedroom.light', paths)

    def test_match_no_results(self):
        result = self.sh.items.match_items('basement.*')
        self.assertEqual(result, [])

    def test_match_with_attr_filter(self):
        result = self.sh.items.match_items('floor.*:my_plugin')
        self.assertEqual(len(result), 3)  # all three have my_plugin

    def test_match_with_attr_and_value(self):
        result = self.sh.items.match_items('floor.*:my_plugin[yes]')
        paths = {i.property.path for i in result}
        self.assertIn('floor.kitchen.light', paths)
        self.assertIn('floor.bedroom.light', paths)
        self.assertNotIn('floor.kitchen.temp', paths)

    def test_match_exact_path(self):
        result = self.sh.items.match_items('floor.kitchen.light')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].property.path, 'floor.kitchen.light')


# ===========================================================================
# _attribute_find
# ===========================================================================

class TestItemsAttributeFind(_ItemsTestBase):

    def setUp(self):
        super().setUp()
        self.items = self.sh.items
        self.attr_list = [
            'avm_identifier',
            'avm_data_type@willy_tel',
            'avm_wlan_index',
            'visu_acl',
        ]

    def test_exact_match(self):
        self.assertTrue(self.items._attribute_find('avm_wlan_index', self.attr_list))

    def test_exact_not_in_list(self):
        self.assertFalse(self.items._attribute_find('unknown_attr', self.attr_list))

    def test_at_suffix_matches_any_starting_with(self):
        # 'avm_data_type@' → any attribute starting with 'avm_data_type@'
        self.assertTrue(self.items._attribute_find('avm_data_type@', self.attr_list))

    def test_at_suffix_also_matches_bare_attr(self):
        # 'avm_wlan_index@' → no 'avm_wlan_index@*' in list but 'avm_wlan_index' is there
        self.assertTrue(self.items._attribute_find('avm_wlan_index@', self.attr_list))

    def test_at_prefix_matches_ending(self):
        # '@willy_tel' → 'avm_data_type@willy_tel' is in list
        self.assertTrue(self.items._attribute_find('@willy_tel', self.attr_list))

    def test_at_prefix_no_match(self):
        # '@fritz_wz' → nothing ends with that
        self.assertFalse(self.items._attribute_find('@fritz_wz', self.attr_list))

    def test_at_prefix_exact_name_not_matched(self):
        # '@visu_acl' → 'visu_acl' does NOT end with '@visu_acl'
        self.assertFalse(self.items._attribute_find('@visu_acl', self.attr_list))

    def test_full_qualified_at_match(self):
        # 'avm_data_type@willy_tel' → exact match
        self.assertTrue(self.items._attribute_find('avm_data_type@willy_tel', self.attr_list))

    def test_full_qualified_at_no_match(self):
        # 'avm_data_type@fritz_wz' → not in list
        self.assertFalse(self.items._attribute_find('avm_data_type@fritz_wz', self.attr_list))

    def test_bare_attr_not_matched_by_at_prefix(self):
        # 'willy_tel' (no @) → check as plain string, not in list
        self.assertFalse(self.items._attribute_find('willy_tel', self.attr_list))


# ===========================================================================
# find_items / find_children
# ===========================================================================

class TestItemsFindItems(_ItemsTestBase):

    def setUp(self):
        super().setUp()
        self.item_a = _make_item(self.sh, 'a', 'foo', zone='living')
        self.item_b = _make_item(self.sh, 'b', 'foo', zone='bedroom')
        self.item_c = _make_item(self.sh, 'c', 'foo')  # no zone attr

    def test_find_items_by_attr(self):
        results = list(self.sh.items.find_items('zone'))
        paths = {i.property.path for i in results}
        self.assertIn('a', paths)
        self.assertIn('b', paths)
        self.assertNotIn('c', paths)

    def test_find_items_no_matches(self):
        results = list(self.sh.items.find_items('nonexistent_attr'))
        self.assertEqual(results, [])


class TestItemsFindChildren(_ItemsTestBase):

    def setUp(self):
        super().setUp()
        # Build a tiny tree: parent has two children, one has a grandchild
        self.parent   = _make_item(self.sh, 'parent',            'foo', sensor_type='temp')
        self.child1   = _make_item(self.sh, 'parent.child1',     'foo', sensor_type='temp')
        self.child2   = _make_item(self.sh, 'parent.child2',     'foo')
        self.grandch  = _make_item(self.sh, 'parent.child1.sub', 'foo', sensor_type='temp')

        # Wire the tree manually (Items doesn't do this automatically in our test setup)
        self.parent._Item__children   = [self.child1, self.child2]
        self.child1._Item__children   = [self.grandch]
        self.child2._Item__children   = []
        self.grandch._Item__children  = []

    def test_find_children_direct_only(self):
        # child1 has sensor_type; child2 does not; grandchild is found recursively
        results = self.sh.items.find_children(self.parent, 'sensor_type')
        paths = {i.property.path for i in results}
        self.assertIn('parent.child1', paths)
        self.assertIn('parent.child1.sub', paths)
        self.assertNotIn('parent.child2', paths)

    def test_find_children_no_match(self):
        results = self.sh.items.find_children(self.parent, 'unknown_conf')
        self.assertEqual(results, [])


# ===========================================================================
# get_toplevel_items
# ===========================================================================

class TestItemsGetToplevelItems(_ItemsTestBase):

    def test_toplevel_empty_initially(self):
        Items._children = []
        result = list(self.sh.items.get_toplevel_items())
        self.assertEqual(result, [])

    def test_toplevel_items_added(self):
        item1 = _make_item(self.sh, 'root1')
        item2 = _make_item(self.sh, 'root2')
        Items._children = [item1, item2]
        result = list(self.sh.items.get_toplevel_items())
        self.assertEqual(len(result), 2)


# ===========================================================================
# remove_item
# ===========================================================================

class TestItemsRemoveItem(_ItemsTestBase):

    def test_remove_existing_item(self):
        item = _make_item(self.sh, 'removeme', 'num')
        self.assertEqual(self.sh.items.item_count(), 1)
        # patch item.remove() → True so no plugin teardown needed
        with patch.object(item, 'remove', return_value=True):
            self.sh.items.remove_item(item)
        self.assertEqual(self.sh.items.item_count(), 0)
        self.assertIsNone(self.sh.items.return_item('removeme'))

    def test_remove_nonexistent_item_is_no_op(self):
        item = lib.item.item.Item(self.sh, self.sh, 'ghost', {'type': 'foo'})
        # not added to Items — should silently return
        self.sh.items.remove_item(item)   # must not raise
        self.assertEqual(self.sh.items.item_count(), 0)


# ===========================================================================
# add_plugin_attribute / add_plugin_attribute_prefix / plugin_attribute_exists
# ===========================================================================

class TestItemsPluginAttributes(_ItemsTestBase):

    def test_add_and_find_plugin_attribute(self):
        attr = {'type': 'bool', 'duplicate_use': False}
        self.sh.items.add_plugin_attribute('myplugin', 'my_attr', attr)
        self.assertTrue(self.sh.items.plugin_attribute_exists('my_attr'))

    def test_unknown_attr_not_found(self):
        self.assertFalse(self.sh.items.plugin_attribute_exists('nonexistent_attr'))

    def test_add_plugin_attribute_prefix(self):
        prefix = {'type': 'str'}
        self.sh.items.add_plugin_attribute_prefix('myplugin', 'my_prefix_', prefix)
        self.assertTrue(self.sh.items.plugin_attribute_exists('my_prefix_anything'))

    def test_duplicate_attr_same_plugin_not_re_added(self):
        attr = {'type': 'bool', 'duplicate_use': False}
        self.sh.items.add_plugin_attribute('plugin_a', 'shared_attr', attr)
        self.sh.items.add_plugin_attribute('plugin_a', 'shared_attr', attr)  # same plugin → ok
        # Should still be registered once under plugin_a
        self.assertEqual(Items.plugin_attributes['shared_attr']['plugin'], 'plugin_a')

    def test_prefix_tuple_regenerated_after_add(self):
        # plugin_prefixes_tuple is lazily built; force regeneration
        Items.plugin_prefixes_tuple = None
        prefix = {'type': 'num'}
        self.sh.items.add_plugin_attribute_prefix('p', 'pfx_', prefix)
        Items.plugin_prefixes_tuple = None  # reset lazy cache
        self.assertTrue(self.sh.items.plugin_attribute_exists('pfx_test'))


# ===========================================================================
# return_struct_definitions (delegates to Structs)
# ===========================================================================

class TestItemsStructDefinitions(_ItemsTestBase):

    def test_returns_dict(self):
        result = self.sh.items.return_struct_definitions()
        self.assertIsInstance(result, dict)

    def test_add_and_return_struct(self):
        struct = collections.OrderedDict([('type', 'num'), ('name', 'test')])
        self.sh.items.add_struct_definition('myplugin', 'mystruct', struct)
        definitions = self.sh.items.return_struct_definitions()
        self.assertIn('myplugin.mystruct', definitions)


if __name__ == '__main__':
    unittest.main()
