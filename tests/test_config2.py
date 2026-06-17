#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Additional tests for lib/config.py (Tier 2 coverage)

Existing test_config.py covers parse_basename YAML reading basics.
This file covers pure-function helpers and the sanitisation pipeline.
"""

import collections
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import lib.config as config


# ===========================================================================
# strip_quotes
# ===========================================================================


class TestStripQuotes(unittest.TestCase):
    def test_double_quotes_stripped(self):
        self.assertEqual(config.strip_quotes('"hello"'), "hello")

    def test_single_quotes_stripped(self):
        self.assertEqual(config.strip_quotes("'hello'"), "hello")

    def test_no_quotes_unchanged(self):
        self.assertEqual(config.strip_quotes("hello"), "hello")

    def test_mismatched_quotes_not_stripped(self):
        self.assertEqual(config.strip_quotes("\"hello'"), "\"hello'")

    def test_internal_quote_not_stripped(self):
        # Only strips when the two outer quotes are the only pair
        self.assertEqual(config.strip_quotes('"he"llo"'), '"he"llo"')

    def test_empty_string(self):
        self.assertEqual(config.strip_quotes(""), "")

    def test_leading_whitespace_stripped_first(self):
        self.assertEqual(config.strip_quotes('  "hello"  '), "hello")

    def test_single_char_in_quotes(self):
        self.assertEqual(config.strip_quotes('"x"'), "x")


# ===========================================================================
# nested_get
# ===========================================================================


class TestNestedGet(unittest.TestCase):
    def setUp(self):
        self.d = {"a": {"b": {"c": "deep"}, "x": 42}, "top": "value"}

    def test_top_level_key(self):
        self.assertEqual(config.nested_get(self.d, "top"), "value")

    def test_two_levels(self):
        self.assertEqual(config.nested_get(self.d, "a.x"), 42)

    def test_three_levels(self):
        self.assertEqual(config.nested_get(self.d, "a.b.c"), "deep")

    def test_missing_key_returns_none(self):
        self.assertIsNone(config.nested_get(self.d, "missing"))

    def test_missing_nested_key_returns_none(self):
        self.assertIsNone(config.nested_get(self.d, "a.b.missing"))

    def test_partial_path_returns_subtree(self):
        result = config.nested_get(self.d, "a.b")
        self.assertEqual(result, {"c": "deep"})


# ===========================================================================
# merge
# ===========================================================================


class TestMerge(unittest.TestCase):
    def _od(self, pairs=None):
        return collections.OrderedDict(pairs or [])

    def test_merge_disjoint_keys(self):
        src = self._od([("b", "B")])
        dst = self._od([("a", "A")])
        result = config.merge(src, dst)
        self.assertEqual(result["a"], "A")
        self.assertEqual(result["b"], "B")

    def test_merge_scalar_source_overwrites_destination(self):
        src = self._od([("key", "from_src")])
        dst = self._od([("key", "from_dst")])
        config.merge(src, dst)
        self.assertEqual(dst["key"], "from_src")

    def test_merge_nested_dicts_recursive(self):
        src = self._od([("outer", self._od([("b", "B")]))])
        dst = self._od([("outer", self._od([("a", "A")]))])
        result = config.merge(src, dst)
        self.assertEqual(result["outer"]["a"], "A")
        self.assertEqual(result["outer"]["b"], "B")

    def test_merge_returns_destination(self):
        src = self._od([("x", "1")])
        dst = self._od()
        result = config.merge(src, dst)
        self.assertIs(result, dst)

    def test_merge_integer_converted_to_string(self):
        src = self._od([("num", 42)])
        dst = self._od()
        config.merge(src, dst)
        self.assertEqual(dst["num"], "42")

    def test_merge_empty_source_unchanged_destination(self):
        src = self._od([])
        dst = self._od([("a", "A")])
        config.merge(src, dst)
        self.assertEqual(len(dst), 1)
        self.assertEqual(dst["a"], "A")

    def test_docstring_example(self):
        # From merge() docstring: b merged into a
        a = self._od([("first", self._od([("all_rows", self._od([("pass", "dog"), ("number", "1")]))]))])
        b = self._od([("first", self._od([("all_rows", self._od([("fail", "cat"), ("number", "5")]))]))])
        result = config.merge(b, a)
        self.assertEqual(result["first"]["all_rows"]["pass"], "dog")
        self.assertEqual(result["first"]["all_rows"]["fail"], "cat")
        self.assertEqual(result["first"]["all_rows"]["number"], "5")


# ===========================================================================
# merge_structlists
# ===========================================================================


class TestMergeStructlists(unittest.TestCase):
    def setUp(self):
        config.struct_merging_active = False
        config.struct_merge_lists = True

    def tearDown(self):
        config.struct_merging_active = False
        config.struct_merge_lists = True

    def test_plain_lists_l2_wins(self):
        result = config.merge_structlists(["a", "b"], ["c", "d"])
        self.assertEqual(result, ["c", "d"])

    def test_both_merge_star_returns_l1(self):
        result = config.merge_structlists(["merge*", "a"], ["merge*", "b"])
        self.assertEqual(result, ["merge*", "a"])

    def test_both_merge_unique_star_deduplicates(self):
        result = config.merge_structlists(["merge_unique*", "a", "a", "b"], ["merge_unique*", "c"])
        # result should not have duplicates in body
        body = result[1:]
        self.assertEqual(len(body), len(set(body)))

    def test_struct_active_first_wins(self):
        config.struct_merging_active = True
        config.struct_merge_lists = False
        result = config.merge_structlists(["a", "b"], ["c", "d"])
        self.assertEqual(result, ["a", "b"])

    def test_struct_active_merge_concatenates(self):
        config.struct_merging_active = True
        config.struct_merge_lists = True
        result = config.merge_structlists(["a"], ["b"])
        self.assertEqual(result, ["a", "b"])


# ===========================================================================
# Sanitisation
# ===========================================================================


class TestRemoveComments(unittest.TestCase):
    def test_removes_comment_leaf(self):
        d = collections.OrderedDict([("comment", "text"), ("real", "v")])
        config.remove_comments(d)
        self.assertNotIn("comment", d)
        self.assertIn("real", d)

    def test_removes_comment_prefixed_leaf(self):
        d = collections.OrderedDict([("comment_note", "x"), ("keep", "y")])
        config.remove_comments(d)
        self.assertNotIn("comment_note", d)

    def test_non_comment_preserved(self):
        d = collections.OrderedDict([("name", "item"), ("type", "num")])
        config.remove_comments(d)
        self.assertEqual(len(d), 2)


class TestRemoveDigits(unittest.TestCase):
    def test_removes_digit_prefixed_leaf(self):
        d = collections.OrderedDict([("1item", "bad"), ("good", "ok")])
        config.remove_digits(d)
        self.assertNotIn("1item", d)
        self.assertIn("good", d)

    def test_removes_digit_prefixed_branch(self):
        d = collections.OrderedDict(
            [
                ("3group", collections.OrderedDict([("child", "x")])),
                ("valid", "yes"),
            ]
        )
        config.remove_digits(d)
        self.assertNotIn("3group", d)
        self.assertIn("valid", d)


class TestRemoveReserved(unittest.TestCase):
    def test_removes_set_branch(self):
        d = collections.OrderedDict(
            [
                ("set", collections.OrderedDict([("a", "1")])),
                ("valid", "ok"),
            ]
        )
        config.remove_reserved(d)
        self.assertNotIn("set", d)
        self.assertIn("valid", d)

    def test_removes_get_branch(self):
        d = collections.OrderedDict(
            [
                ("get", collections.OrderedDict()),
            ]
        )
        config.remove_reserved(d)
        self.assertNotIn("get", d)

    def test_non_reserved_leaf_kept(self):
        # 'set' as a leaf value (not a branch) — should stay since
        # remove_reserved only targets REMOVE_PATH (branch nodes)
        d = collections.OrderedDict([("mykey", "set")])
        config.remove_reserved(d)
        self.assertIn("mykey", d)


class TestRemoveKeyword(unittest.TestCase):
    def test_removes_if_branch(self):
        d = collections.OrderedDict(
            [
                ("if", collections.OrderedDict([("x", "1")])),
                ("item", "ok"),
            ]
        )
        config.remove_keyword(d)
        self.assertNotIn("if", d)
        self.assertIn("item", d)

    def test_removes_for_branch(self):
        d = collections.OrderedDict([("for", collections.OrderedDict())])
        config.remove_keyword(d)
        self.assertNotIn("for", d)

    def test_non_keyword_kept(self):
        d = collections.OrderedDict([("temperature", "v")])
        config.remove_keyword(d)
        self.assertIn("temperature", d)


class TestSanitizeItems(unittest.TestCase):
    def test_combined_sanitisation(self):
        d = collections.OrderedDict(
            [
                ("comment_note", "ignore"),
                ("1bad", "ignore"),
                ("good_item", "keep"),
            ]
        )
        config.sanitize_items(d)
        self.assertNotIn("comment_note", d)
        self.assertNotIn("1bad", d)
        self.assertIn("good_item", d)

    def test_empty_dict_safe(self):
        d = collections.OrderedDict()
        config.sanitize_items(d)
        self.assertEqual(len(d), 0)


# ===========================================================================
# parse_basename (file-based)
# ===========================================================================


class TestParseBasename(unittest.TestCase):
    def _write(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        f.write(textwrap.dedent(content))
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name[:-5]  # strip .yaml; parse_basename appends it

    def test_loads_simple_config(self):
        path = self._write("""
            item1:
                type: num
        """)
        result = config.parse_basename(path)
        self.assertIn("item1", result)
        self.assertEqual(result["item1"]["type"], "num")

    def test_missing_file_returns_empty_dict(self):
        result = config.parse_basename("/nonexistent/no_file")
        self.assertEqual(result, {})

    def test_removes_comments_during_parse(self):
        path = self._write("""
            item1:
                type: str
                comment: should be removed
        """)
        result = config.parse_basename(path)
        self.assertNotIn("comment", result.get("item1", {}))

    def test_removes_digit_prefixed_keys(self):
        path = self._write("""
            good_item:
                type: num
            1bad_item:
                type: num
        """)
        result = config.parse_basename(path)
        self.assertIn("good_item", result)
        self.assertNotIn("1bad_item", result)

    def test_nested_structure_preserved(self):
        path = self._write("""
            parent:
                child:
                    type: bool
        """)
        result = config.parse_basename(path)
        self.assertIn("child", result.get("parent", {}))

    def test_multiple_top_level_items(self):
        path = self._write("""
            alpha:
                type: num
            beta:
                type: str
            gamma:
                type: bool
        """)
        result = config.parse_basename(path)
        self.assertIn("alpha", result)
        self.assertIn("beta", result)
        self.assertIn("gamma", result)


if __name__ == "__main__":
    unittest.main()
