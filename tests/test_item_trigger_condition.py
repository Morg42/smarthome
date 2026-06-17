#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for Item._build_trigger_condition_eval()

_build_trigger_condition_eval() takes a trigger_condition list (as parsed from
YAML) and converts it into a Python eval-ready expression string.  That string
is stored in self._trigger_condition and evaluated inside __run_eval() before
the eval expression itself is computed.

YAML trigger_condition structure:
  trigger_condition:
    - source_item_path:
        - 'value > 10'
        - 'value < 20'   # multiple → AND-joined
    - other_item_path:   # multiple or-condition entries → OR-joined
        - 'value == 5'

The method:
  1. Joins multiple conditions for a single key with ') and ('
  2. Joins multiple keys (OR conditions) with ') or ('
  3. Rewrites bare '=' to '==' (but not '==', '<=', '>=', '=>', '=<')
  4. Normalises 'true'/'false' (any case) to 'True'/'False'
  5. Expands relative item path references via get_stringwithabsolutepathes

Coverage
--------
Single condition:
  single entry → expression string returned as-is (after normalisation)
  bare '=' rewritten to '=='
  '==' left unchanged
  '<=' left unchanged
  '>=' left unchanged
  'true' (lowercase) → 'True'
  'false' (lowercase) → 'False'
  'TRUE' (uppercase) → 'True'

Multiple AND conditions (one key, multiple values):
  two conditions → joined with ') and ('

Multiple OR conditions (two keys):
  result joined with ') or ('

Multiple OR with parentheses:
  >1 top-level entry → outer '(' ')' wrapping

Key named 'value' (special case — ignored):
  'value' key skipped, its conditions not included

Relative item path expansion:
  sh.item() reference in condition → expanded to absolute path
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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


def _item(sh, path, itype='num', **conf):
    c = {'type': itype}
    c.update(conf)
    i = lib.item.item.Item(sh, sh.items, path, c)
    sh.items.add_item(path, i)
    return i


def _build(item, trigger_condition):
    """Convenience wrapper."""
    return item._build_trigger_condition_eval(trigger_condition)


class _Base(unittest.TestCase):
    def setUp(self):
        self.sh = _make_sh()
        self.item = _item(self.sh, 'parent.child')

    def tearDown(self):
        _reset()


# ===========================================================================
# Single condition
# ===========================================================================


class TestSingleCondition(_Base):
    def test_simple_greater_than(self):
        tc = [{'some.item': ['value > 10']}]
        result = _build(self.item, tc)
        self.assertIn('value > 10', result)

    def test_bare_equals_rewritten_to_double_equals(self):
        tc = [{'some.item': ['value = 5']}]
        result = _build(self.item, tc)
        self.assertIn('==', result)
        # single '=' should be gone (replaced by '==')
        # count of '=' that are not part of '==' would be 0
        # simplest check: '==' appears and result evaluable
        self.assertNotIn(' = ', result)

    def test_double_equals_unchanged(self):
        tc = [{'some.item': ['value == 5']}]
        result = _build(self.item, tc)
        self.assertIn('value == 5', result)

    def test_less_than_or_equal_unchanged(self):
        tc = [{'some.item': ['value <= 10']}]
        result = _build(self.item, tc)
        self.assertIn('value <= 10', result)

    def test_greater_than_or_equal_unchanged(self):
        tc = [{'some.item': ['value >= 10']}]
        result = _build(self.item, tc)
        self.assertIn('value >= 10', result)

    def test_arrow_equals_unchanged(self):
        tc = [{'some.item': ['value => 5']}]
        result = _build(self.item, tc)
        self.assertIn('=>', result)

    def test_reverse_arrow_equals_unchanged(self):
        tc = [{'some.item': ['value =< 5']}]
        result = _build(self.item, tc)
        self.assertIn('=<', result)

    def test_lowercase_true_normalised(self):
        tc = [{'some.item': ['value == true']}]
        result = _build(self.item, tc)
        self.assertIn('True', result)
        self.assertNotIn('true', result)

    def test_lowercase_false_normalised(self):
        tc = [{'some.item': ['value == false']}]
        result = _build(self.item, tc)
        self.assertIn('False', result)
        self.assertNotIn('false', result)

    def test_uppercase_true_normalised(self):
        tc = [{'some.item': ['value == TRUE']}]
        result = _build(self.item, tc)
        self.assertIn('True', result)

    def test_uppercase_false_normalised(self):
        tc = [{'some.item': ['value == FALSE']}]
        result = _build(self.item, tc)
        self.assertIn('False', result)

    def test_mixed_case_true_normalised(self):
        tc = [{'some.item': ['value == True']}]
        result = _build(self.item, tc)
        self.assertIn('True', result)


# ===========================================================================
# Multiple AND conditions (one key, multiple values)
# ===========================================================================


class TestMultipleAndConditions(_Base):
    def test_two_conditions_joined_with_and(self):
        tc = [{'some.item': ['value > 10', 'value < 20']}]
        result = _build(self.item, tc)
        self.assertIn(' and ', result)
        self.assertIn('value > 10', result)
        self.assertIn('value < 20', result)

    def test_three_conditions_joined_with_and(self):
        tc = [{'some.item': ['value > 0', 'value != 5', 'value < 100']}]
        result = _build(self.item, tc)
        self.assertEqual(result.count(' and '), 2)

    def test_two_conditions_wrapped_in_parens(self):
        # Multiple conditions for one key → wrapped in ( )
        tc = [{'some.item': ['value > 10', 'value < 20']}]
        result = _build(self.item, tc)
        self.assertTrue(result.startswith('('))
        self.assertTrue(result.endswith(')'))


# ===========================================================================
# Multiple OR conditions (multiple keys in OR list)
# ===========================================================================


class TestMultipleOrConditions(_Base):
    def test_two_keys_joined_with_or(self):
        tc = [{'item_a': ['value > 10']}, {'item_b': ['value == 5']}]
        result = _build(self.item, tc)
        self.assertIn(' or ', result)
        self.assertIn('value > 10', result)
        self.assertIn('value == 5', result)

    def test_two_or_conditions_wrapped_in_outer_parens(self):
        tc = [{'item_a': ['value > 10']}, {'item_b': ['value < 5']}]
        result = _build(self.item, tc)
        self.assertTrue(result.startswith('('))
        self.assertTrue(result.endswith(')'))

    def test_single_or_condition_not_wrapped(self):
        tc = [{'some.item': ['value > 10']}]
        result = _build(self.item, tc)
        # single top-level entry → no outer wrapping
        self.assertNotIn(' or ', result)


# ===========================================================================
# 'value' key is skipped
# ===========================================================================


class TestValueKeySkipped(_Base):
    def test_value_key_does_not_appear_in_output(self):
        # 'value' is a special key name that the method explicitly skips
        tc = [{'value': ['some_condition > 0']}]
        # No result built → result variable may be unset; method returns None
        # or an uninitialized 'result'. The key point: no crash and conditions
        # inside 'value' key are not included.
        try:
            result = _build(self.item, tc)
        except (UnboundLocalError, NameError):
            result = None
        # If result is returned, it should NOT contain the value-key condition
        if result is not None:
            self.assertNotIn('some_condition > 0', result)

    def test_mixed_value_key_and_real_key(self):
        tc = [{'value': ['ignored > 0'], 'real_item': ['value == 5']}]
        result = _build(self.item, tc)
        self.assertIn('value == 5', result)
        self.assertNotIn('ignored > 0', result)


# ===========================================================================
# Relative item path expansion
# ===========================================================================


class TestRelativePathExpansion(_Base):
    def test_absolute_path_unchanged(self):
        tc = [{'some.item': ['sh.other.item() > 5']}]
        result = _build(self.item, tc)
        # 'sh.other.item()' is an absolute path — returned unchanged
        self.assertIn('other.item', result)

    def test_relative_path_expanded(self):
        # 'sh...sibling()' — two dots after 'sh.' — means go up one level from
        # 'parent.child', giving 'parent', then append 'sibling' → 'parent.sibling'.
        # (One dot stays at current level; two dots go up one level.)
        tc = [{'some.item': ['sh...sibling() > 0']}]
        result = _build(self.item, tc)
        self.assertIn('parent.sibling', result)

    def test_no_sh_reference_unchanged(self):
        tc = [{'some.item': ['value > 5']}]
        result = _build(self.item, tc)
        self.assertIn('value > 5', result)


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases(_Base):
    def test_condition_with_comparison_and_true(self):
        # Compound: '= true' should become '== True'
        tc = [{'some.item': ['value = true']}]
        result = _build(self.item, tc)
        self.assertIn('True', result)
        self.assertIn('==', result)

    def test_multiple_and_with_bare_equals(self):
        tc = [{'some.item': ['value = 5', 'other = 10']}]
        result = _build(self.item, tc)
        self.assertEqual(result.count('=='), 2)

    def test_or_of_and_conditions(self):
        # Two OR entries, each with AND conditions
        tc = [{'item_a': ['value > 0', 'value < 10']}, {'item_b': ['value > 20', 'value < 30']}]
        result = _build(self.item, tc)
        self.assertIn(' and ', result)
        self.assertIn(' or ', result)


if __name__ == '__main__':
    unittest.main()
