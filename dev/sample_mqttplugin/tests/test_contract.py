"""
Contract tests for the sample_mqttplugin example.

This file demonstrates how to wire up the plugin_contract test framework for a
plugin based on MqttPlugin.  When you copy this sample to plugins/myplugin/,
adapt as follows:

    from plugins.myplugin import MyMqttPlugin      # rename class

    class TestMyMqttPlugin(BasePluginContractTest,
                           YamlPluginContractTest,
                           MqttPluginContractTest):
        PLUGIN_CLASS = MyMqttPlugin
        PLUGIN_INIT_PARAMS = {}
        ITEM_ATTR_SETS = [
            {'my_item_attr': 'value'},
        ]
"""

import os
import sys

# ensure shng root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from tests.plugin_contract.base      import BasePluginContractTest
from tests.plugin_contract.with_yaml import YamlPluginContractTest
from tests.plugin_contract.mqtt      import MqttPluginContractTest
from dev.sample_mqttplugin import SampleMqttPlugin


class TestSampleMqttPlugin(BasePluginContractTest, YamlPluginContractTest, MqttPluginContractTest):
    """
    Tier 1 + Tier 2 + Tier 3 contract tests for the sample_mqttplugin example.

    MqttPluginContractTest.setUp() patches lib.module.Modules so that
    get_module('mqtt') returns a MockMqttModule — no real broker needed.
    """

    PLUGIN_CLASS = SampleMqttPlugin
    PLUGIN_INIT_PARAMS = {}
    # foo_itemid is the item attribute declared in plugin.yaml.
    # An item carrying this attribute should be registered by parse_item().
    ITEM_ATTR_SETS = [
        {'foo_itemid': 'SHELLYPLUGS-AA1122'},
    ]
