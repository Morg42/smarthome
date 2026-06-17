"""
Contract tests for the sample_plugin example.

This file demonstrates how to wire up the plugin_contract test framework for a
plugin based on SmartPlugin.  When you copy this sample to plugins/myplugin/,
adapt as follows:

    from plugins.myplugin import MyPlugin          # rename class

    class TestMyPlugin(BasePluginContractTest, YamlPluginContractTest):
        PLUGIN_CLASS = MyPlugin
        PLUGIN_INIT_PARAMS = {'param3': 'required'}   # fill in mandatory params
        ITEM_ATTR_SETS = [
            {'my_item_attr': 'value'},               # minimal set that registers an item
        ]
"""

import os
import sys

# ensure shng root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from tests.plugin_contract.base import BasePluginContractTest
from tests.plugin_contract.with_yaml import YamlPluginContractTest
from dev.sample_plugin import SamplePlugin


class TestSamplePlugin(BasePluginContractTest, YamlPluginContractTest):
    """
    Tier 1 + Tier 2 contract tests for the sample_plugin example.

    param3 is declared mandatory in plugin.yaml (no default), so we must
    supply it in PLUGIN_INIT_PARAMS.
    """

    PLUGIN_CLASS = SamplePlugin
    PLUGIN_INIT_PARAMS = {
        "param3": "required_test_value",
    }
    # foo_itemtag is the single item attribute declared in plugin.yaml.
    # Providing it here allows test_item_attr_sets_register_items to verify
    # that parse_item() actually registers a matching item.
    ITEM_ATTR_SETS = [
        {"foo_itemtag": "demo"},
    ]
