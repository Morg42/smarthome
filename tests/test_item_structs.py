#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for lib/item/structs.py

Strategy
--------
Structs.__init__ calls self._sh.get_config_dir() and os-level path ops.
We bypass __init__ entirely using __new__ + manual attribute setup so we
can test the pure-logic methods (merge, merge_structlists,
add_struct_definition, return_struct_definitions, resolve_structs,
merge_substruct_to_struct, traverse_struct, process_struct_node)
without needing a full filesystem layout.

Coverage
--------
merge_structlists
merge
add_struct_definition
return_struct_definitions
merge_substruct_to_struct
resolve_structs
traverse_struct / process_struct_node
"""

import collections
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tests.common as common

common.register_shng_log_levels()

import lib.item.structs as _structs_module
from lib.item.structs import Structs


# ---------------------------------------------------------------------------
# Helper: create a Structs object without __init__
# ---------------------------------------------------------------------------


def _reset_structs_class():
    """Reset Structs class-level state so tests don't bleed into each other."""
    Structs._struct_definitions = collections.OrderedDict()
    Structs._finalized_structs = []


def _make_structs():
    """Bare Structs instance with class-level state reset."""
    _reset_structs_class()

    s = Structs.__new__(Structs)
    s.logger = logging.getLogger("test.structs")
    s._sh = MagicMock()
    s.save_joined_structs = False
    s.etc_dir = "/tmp/test_etc"
    s.structs_dir = "/tmp/test_structs"
    return s


class _StructsTestBase(unittest.TestCase):
    """Mixin that resets Structs class-level state both before and after each test.

    Structs uses class-level _struct_definitions / _finalized_structs, so state
    set during one test would otherwise bleed into subsequent test files.
    """

    def setUp(self):
        self.s = _make_structs()

    def tearDown(self):
        _reset_structs_class()


def _od(*pairs):
    """Shorthand for an OrderedDict."""
    return collections.OrderedDict(pairs)


# ===========================================================================
# merge_structlists
# ===========================================================================


class TestMergeStructlists(_StructsTestBase):
    def test_two_lists(self):
        result = self.s.merge_structlists([1, 2], [3, 4])
        self.assertEqual(result, [1, 2, 3, 4])

    def test_first_scalar_converted(self):
        result = self.s.merge_structlists("a", ["b", "c"])
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertEqual(len(result), 3)

    def test_second_scalar_converted(self):
        result = self.s.merge_structlists(["a", "b"], "c")
        self.assertEqual(result, ["a", "b", "c"])

    def test_both_scalars(self):
        result = self.s.merge_structlists("x", "y")
        self.assertEqual(result, ["x", "y"])

    def test_empty_lists(self):
        result = self.s.merge_structlists([], [])
        self.assertEqual(result, [])

    def test_preserves_order(self):
        result = self.s.merge_structlists([1, 2, 3], [4, 5])
        self.assertEqual(result, [1, 2, 3, 4, 5])


# ===========================================================================
# merge
# ===========================================================================


class TestMerge(_StructsTestBase):
    def test_adds_new_key(self):
        src = _od(("extra", "value"))
        dst = _od(("existing", "yes"))
        result = self.s.merge(src, dst)
        self.assertIn("extra", result)
        self.assertIn("existing", result)

    def test_destination_wins_on_conflict(self):
        src = _od(("key", "source_val"))
        dst = _od(("key", "dest_val"))
        result = self.s.merge(src, dst)
        self.assertEqual(result["key"], "dest_val")

    def test_nested_ordereddicts_merged_recursively(self):
        src = _od(("child", _od(("a", "1"), ("b", "2"))))
        dst = _od(("child", _od(("b", "dest"), ("c", "3"))))
        result = self.s.merge(src, dst)
        # 'b' is in dst → dst wins; 'a' is only in src → added; 'c' only in dst → kept
        self.assertIn("a", result["child"])
        self.assertEqual(result["child"]["b"], "dest")
        self.assertEqual(result["child"]["c"], "3")

    def test_list_in_source_merged(self):
        src = _od(("tags", ["a", "b"]))
        dst = _od(("tags", ["c"]))
        result = self.s.merge(src, dst)
        self.assertIn("a", result["tags"])
        self.assertIn("c", result["tags"])

    def test_list_only_in_source_added(self):
        src = _od(("tags", ["a", "b"]))
        dst = _od()
        result = self.s.merge(src, dst)
        self.assertEqual(result["tags"], ["a", "b"])

    def test_struct_is_optional_key_skipped(self):
        src = _od(("__struct_is_optional", True), ("real_key", "val"))
        dst = _od()
        result = self.s.merge(src, dst)
        self.assertNotIn("__struct_is_optional", result)
        self.assertIn("real_key", result)

    def test_returns_destination(self):
        src = _od(("k", "v"))
        dst = _od()
        result = self.s.merge(src, dst)
        self.assertIs(result, dst)

    def test_none_destination_value_replaced(self):
        # When node == 'None', replace with source value (not recurse)
        src = _od(("child", _od(("x", "1"))))
        dst = _od(("child", "None"))
        result = self.s.merge(src, dst)
        self.assertEqual(result["child"], _od(("x", "1")))


# ===========================================================================
# add_struct_definition
# ===========================================================================


class TestAddStructDefinition(_StructsTestBase):
    def test_add_basic_struct(self):
        struct = _od(("type", "num"), ("name", "sensor"))
        self.s.add_struct_definition("myplugin", "mysensor", struct)
        self.assertIn("myplugin.mysensor", Structs._struct_definitions)

    def test_struct_gets_optional_flag(self):
        struct = _od(("type", "bool"))
        self.s.add_struct_definition("p", "x", struct, optional=True)
        self.assertTrue(Structs._struct_definitions["p.x"]["__struct_is_optional"])

    def test_struct_not_optional_by_default(self):
        struct = _od(("type", "str"))
        self.s.add_struct_definition("p", "y", struct)
        self.assertFalse(Structs._struct_definitions["p.y"]["__struct_is_optional"])

    def test_empty_plugin_name_uses_struct_name_directly(self):
        struct = _od(("type", "num"))
        self.s.add_struct_definition("", "global_struct", struct)
        self.assertIn("global_struct", Structs._struct_definitions)

    def test_duplicate_non_optional_ignored(self):
        struct1 = _od(("type", "num"))
        struct2 = _od(("type", "str"))
        self.s.add_struct_definition("p", "s", struct1)
        self.s.add_struct_definition("p", "s", struct2, from_dir="plugins")
        # Second one with from_dir='plugins' should be silently ignored
        self.assertEqual(Structs._struct_definitions["p.s"]["type"], "num")

    def test_optional_overwritten_by_mandatory(self):
        struct_opt = _od(("type", "num"))
        struct_mand = _od(("type", "str"))
        self.s.add_struct_definition("p", "t", struct_opt, optional=True)
        self.s.add_struct_definition("p", "t", struct_mand, optional=False)
        # mandatory should replace optional
        self.assertEqual(Structs._struct_definitions["p.t"]["type"], "str")
        self.assertFalse(Structs._struct_definitions["p.t"]["__struct_is_optional"])


# ===========================================================================
# return_struct_definitions
# ===========================================================================


class TestReturnStructDefinitions(_StructsTestBase):
    def test_empty_returns_empty_dict(self):
        result = self.s.return_struct_definitions()
        self.assertEqual(result, {})

    def test_public_struct_included(self):
        struct = _od(("type", "num"))
        self.s.add_struct_definition("p", "visible", struct)
        result = self.s.return_struct_definitions()
        self.assertIn("p.visible", result)

    def test_internal_struct_excluded_by_default(self):
        # Internal structs have a name starting with '_'
        struct = _od(("type", "num"))
        # add with a name that will produce a struct_name starting with '_'
        Structs._struct_definitions["myplug._internal"] = struct
        result = self.s.return_struct_definitions(all=False)
        self.assertNotIn("myplug._internal", result)

    def test_internal_struct_included_when_all_true(self):
        struct = _od(("type", "num"))
        Structs._struct_definitions["myplug._internal"] = struct
        result = self.s.return_struct_definitions(all=True)
        self.assertIn("myplug._internal", result)

    def test_struct_without_dot_uses_full_name(self):
        Structs._struct_definitions["toplevel"] = _od(("type", "num"))
        result = self.s.return_struct_definitions()
        self.assertIn("toplevel", result)


# ===========================================================================
# merge_substruct_to_struct
# ===========================================================================


class TestMergeSubstructToStruct(_StructsTestBase):
    def setUp(self):
        super().setUp()
        # Register a substruct for use in tests
        Structs._struct_definitions["base.common"] = _od(
            ("name", "default_name"),
            ("unit", "celsius"),
            ("__struct_is_optional", False),
        )

    def test_substruct_keys_added_to_main(self):
        main = _od(("type", "num"))
        self.s.merge_substruct_to_struct(main, "base.common", "test_struct")
        self.assertIn("name", main)
        self.assertIn("unit", main)

    def test_main_struct_keys_not_overwritten(self):
        main = _od(("name", "my_name"), ("type", "num"))
        self.s.merge_substruct_to_struct(main, "base.common", "test_struct")
        self.assertEqual(main["name"], "my_name")  # kept from main

    def test_optional_flag_not_copied(self):
        main = _od(("type", "num"))
        self.s.merge_substruct_to_struct(main, "base.common", "test_struct")
        self.assertNotIn("__struct_is_optional", main)

    def test_missing_substruct_logged(self):
        main = _od(("type", "num"))
        # Should log an error but not raise
        self.s.merge_substruct_to_struct(main, "does.not.exist", "test_struct")
        # main is unchanged
        self.assertNotIn("name", main)

    def test_relative_substruct_name(self):
        Structs._struct_definitions["base.relative"] = _od(("extra", "val"), ("__struct_is_optional", False))
        main = _od(("type", "num"))
        # Relative name starting with '.' should be resolved against key_prefix
        self.s.merge_substruct_to_struct(main, ".relative", "test", key_prefix="base")
        self.assertIn("extra", main)

    def test_list_values_merged(self):
        Structs._struct_definitions["base.listprovider"] = _od(
            ("tags", ["a", "b"]),
            ("__struct_is_optional", False),
        )
        main = _od(("tags", ["c"]))
        self.s.merge_substruct_to_struct(main, "base.listprovider", "test")
        self.assertIn("a", main["tags"])
        self.assertIn("c", main["tags"])


# ===========================================================================
# resolve_structs
# ===========================================================================


class TestResolveStructs(_StructsTestBase):
    def setUp(self):
        super().setUp()
        Structs._struct_definitions["plug.base"] = _od(
            ("unit", "V"),
            ("precision", "2"),
            ("__struct_is_optional", False),
        )

    def test_resolve_copies_existing_attributes(self):
        struct = _od(("type", "num"), ("struct", "plug.base"))
        result = self.s.resolve_structs(struct, "test", ["plug.base"], "plug")
        self.assertIn("type", result)

    def test_resolve_merges_substruct(self):
        struct = _od(("type", "num"), ("struct", "plug.base"))
        result = self.s.resolve_structs(struct, "test", ["plug.base"], "plug")
        self.assertIn("unit", result)
        self.assertIn("precision", result)

    def test_resolve_main_wins_on_conflict(self):
        struct = _od(("unit", "A"), ("struct", "plug.base"))
        result = self.s.resolve_structs(struct, "test", ["plug.base"], "plug")
        self.assertEqual(result["unit"], "A")  # main value kept


# ===========================================================================
# traverse_struct / process_struct_node
# ===========================================================================


class TestTraverseStruct(_StructsTestBase):
    def test_traverse_nonexistent_struct(self):
        result = self.s.traverse_struct("does.not.exist")
        self.assertIsNone(result)

    def test_traverse_struct_without_struct_attr_returns_false(self):
        Structs._struct_definitions["plug.simple"] = _od(
            ("type", "num"),
            ("name", "sensor"),
        )
        result = self.s.traverse_struct("plug.simple")
        self.assertFalse(result)

    def test_traverse_struct_with_struct_attr_returns_true(self):
        Structs._struct_definitions["plug.base"] = _od(
            ("unit", "V"),
            ("__struct_is_optional", False),
        )
        Structs._struct_definitions["plug.composite"] = _od(
            ("type", "num"),
            ("struct", "plug.base"),
        )
        result = self.s.traverse_struct("plug.composite")
        self.assertTrue(result)
        # After traversal the 'struct' key should be removed
        self.assertNotIn("struct", Structs._struct_definitions["plug.composite"])

    def test_process_struct_node_no_struct_attr_returns_none(self):
        node = _od(("type", "num"), ("name", "x"))
        result = self.s.process_struct_node(node, "test")
        self.assertIsNone(result)

    def test_process_struct_node_nested_dict_processed(self):
        Structs._struct_definitions["p.sub"] = _od(
            ("extra", "val"),
            ("__struct_is_optional", False),
        )
        node = _od(
            ("child", _od(("struct", "p.sub"), ("own_key", "own_val"))),
        )
        result = self.s.process_struct_node(node, "test", key_prefix="p")
        self.assertIsNotNone(result)
        self.assertIn("extra", result["child"])
        self.assertNotIn("struct", result["child"])


if __name__ == "__main__":
    unittest.main()
