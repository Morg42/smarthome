"""
tests.plugin_contract.mqtt — Tier 3: contract tests for MqttPlugin subclasses.

These tests verify the MQTT-specific contract of plugins that inherit from
lib.model.mqttplugin.MqttPlugin.  They use a lightweight mock MQTT module
so no real broker is needed.

Usage::

    from tests.plugin_contract.base import BasePluginContractTest
    from tests.plugin_contract.mqtt import MqttPluginContractTest
    from plugins.my_mqtt_plugin import MyMqttPlugin


    class TestMyMqttPlugin(BasePluginContractTest, MqttPluginContractTest):
        PLUGIN_CLASS = MyMqttPlugin
        PLUGIN_INIT_PARAMS = {'host': 'localhost'}

The setUp() in MqttPluginContractTest patches lib.module.Modules so that
get_module('mqtt') returns a MockMqttModule instance.  The patch is active
for every test method in the class and is torn down automatically.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import tests.common as common

common.register_shng_log_levels()

from tests.mock.core import MockSmartHome
from tests.plugin_contract._mockitem import MockItem
from tests.plugin_contract.base import make_plugin_instance
from lib.model.mqttplugin import MqttPlugin


# ---------------------------------------------------------------------------
# Mock MQTT module
# ---------------------------------------------------------------------------


class MockMqttModule:
    """
    Minimal stand-in for lib.module.mqtt.Mqtt.

    Records calls so tests can assert on subscribe/unsubscribe/publish
    interactions without needing a real broker.
    """

    _shortname = 'mqtt'

    def __init__(self):
        self.subscribed: list[tuple] = []  # (caller, topic) pairs
        self.unsubscribed: list[tuple] = []
        self.published: list[tuple] = []

    def subscribe_topic(self, caller, topic, callback=None, qos=None, payload_type=None, bool_values=None):
        self.subscribed.append((caller, topic))

    def unsubscribe_topic(self, caller, topic):
        self.unsubscribed.append((caller, topic))

    def publish_topic(self, caller, topic, payload, qos=None, retain=False, bool_values=None):
        self.published.append((caller, topic, payload))

    def get_broker_config(self) -> dict:
        return {'host': 'localhost', 'port': 1883}

    def get_broker_info(self) -> tuple:
        return ({'uptime': '0'}, False)


# ---------------------------------------------------------------------------
# Tier 3 mix-in
# ---------------------------------------------------------------------------


class MqttPluginContractTest(unittest.TestCase):
    """Mix-in: MQTT contract tests for MqttPlugin subclasses."""

    PLUGIN_CLASS: type | None = None
    PLUGIN_INIT_PARAMS: dict = {}

    # -----------------------------------------------------------------------
    # Setup: patch Modules so MqttPlugin.__init__ finds the mock mqtt module
    # -----------------------------------------------------------------------

    def setUp(self):
        if self.PLUGIN_CLASS is None:
            self.skipTest('PLUGIN_CLASS not set')

        self.mock_mqtt = MockMqttModule()
        mock_modules = MagicMock()
        mock_modules.get_module.side_effect = lambda name: self.mock_mqtt if name == 'mqtt' else None

        self._modules_patcher = patch('lib.module.Modules.get_instance', return_value=mock_modules)
        self._modules_patcher.start()

        # Plugin instantiation is delegated to BasePluginContractTest.setUp via
        # cooperative super() call.  The patch is now active so MqttPlugin.__init__
        # will find the mock mqtt module when it calls Modules.get_instance().
        super().setUp()

    def tearDown(self):
        super().tearDown()
        if hasattr(self, '_modules_patcher'):
            self._modules_patcher.stop()

    def _make_item(self, path: str = 'mqtt.test', conf: dict | None = None) -> MockItem:
        return MockItem(path, conf)

    # -----------------------------------------------------------------------
    # Class-level
    # -----------------------------------------------------------------------

    def test_inherits_from_mqttplugin(self):
        """Plugin must inherit from MqttPlugin."""
        self.assertTrue(
            issubclass(self.PLUGIN_CLASS, MqttPlugin), f'{self.PLUGIN_CLASS.__name__} does not inherit from MqttPlugin'
        )

    # -----------------------------------------------------------------------
    # Post-__init__ state
    # -----------------------------------------------------------------------

    def test_mod_mqtt_set_after_init(self):
        """mod_mqtt must be set (not None) when the mqtt module is available."""
        self.assertIsNotNone(
            self.plugin.mod_mqtt, 'mod_mqtt is None after __init__ — mqtt module mock not wired correctly'
        )

    def test_subscribed_topics_empty_after_init(self):
        """_subscribed_topics must be empty after __init__."""
        self.assertEqual(self.plugin._subscribed_topics, {})

    def test_subscriptions_not_started_after_init(self):
        """_subscriptions_started must be False after __init__."""
        self.assertFalse(self.plugin._subscriptions_started)

    # -----------------------------------------------------------------------
    # add_subscription
    # -----------------------------------------------------------------------

    def test_add_subscription_registers_topic(self):
        """add_subscription() stores the topic in _subscribed_topics."""
        item = self._make_item('mqtt.a')
        self.plugin.add_subscription('home/temp', 'num', item=item)
        self.assertIn('home/temp', self.plugin._subscribed_topics)

    def test_add_subscription_with_item_stores_item_path(self):
        """The item path appears as a key under the topic entry."""
        item = self._make_item('mqtt.b')
        self.plugin.add_subscription('home/light', 'bool', item=item)
        self.assertIn(item.property.path, self.plugin._subscribed_topics['home/light'])

    def test_add_subscription_no_item_uses_sentinel(self):
        """add_subscription without item uses '*no_item*' sentinel key."""
        self.plugin.add_subscription('home/event', 'str', callback=lambda *a: None)
        self.assertIn('*no_item*', self.plugin._subscribed_topics['home/event'])

    # -----------------------------------------------------------------------
    # start_subscriptions / stop_subscriptions
    # -----------------------------------------------------------------------

    def test_start_subscriptions_calls_subscribe_topic(self):
        """start_subscriptions() calls mod_mqtt.subscribe_topic for each subscription."""
        item = self._make_item('mqtt.c')
        self.plugin.add_subscription('test/topic', 'str', item=item)
        self.plugin.start_subscriptions()
        self.assertTrue(
            len(self.mock_mqtt.subscribed) >= 1, 'subscribe_topic was never called after start_subscriptions()'
        )

    def test_subscriptions_started_true_after_start(self):
        """_subscriptions_started is True after start_subscriptions()."""
        self.plugin.start_subscriptions()
        self.assertTrue(self.plugin._subscriptions_started)

    def test_stop_subscriptions_calls_unsubscribe_topic(self):
        """stop_subscriptions() calls mod_mqtt.unsubscribe_topic for each subscription."""
        item = self._make_item('mqtt.d')
        self.plugin.add_subscription('test/unsub', 'str', item=item)
        self.plugin.start_subscriptions()
        self.plugin.stop_subscriptions()
        self.assertTrue(
            len(self.mock_mqtt.unsubscribed) >= 1, 'unsubscribe_topic was never called after stop_subscriptions()'
        )

    def test_subscriptions_started_false_after_stop(self):
        """_subscriptions_started is False after stop_subscriptions()."""
        self.plugin.start_subscriptions()
        self.plugin.stop_subscriptions()
        self.assertFalse(self.plugin._subscriptions_started)

    # -----------------------------------------------------------------------
    # _on_mqtt_message
    # -----------------------------------------------------------------------

    def test_on_mqtt_message_updates_item_value(self):
        """_on_mqtt_message() must call item(payload) for subscribed items."""
        item = self._make_item('mqtt.e')
        self.plugin.add_subscription('home/temp', 'num', item=item)
        self.plugin._on_mqtt_message('home/temp', 21.5)
        self.assertEqual(item(), 21.5)

    def test_on_mqtt_message_unknown_topic_does_not_raise(self):
        """_on_mqtt_message() with an unregistered topic must not raise."""
        try:
            self.plugin._on_mqtt_message('unknown/topic', 'payload')
        except Exception as exc:
            self.fail(f'_on_mqtt_message() raised for unknown topic: {exc}')

    # -----------------------------------------------------------------------
    # publish_topic
    # -----------------------------------------------------------------------

    def test_publish_topic_calls_mod_mqtt(self):
        """publish_topic() must delegate to mod_mqtt.publish_topic."""
        self.plugin.publish_topic('test/out', 42)
        self.assertTrue(
            any(t == 'test/out' for _, t, _ in self.mock_mqtt.published), 'mod_mqtt.publish_topic was not called'
        )

    def test_publish_topic_updates_item_values_dict(self):
        """publish_topic() with an item updates _item_values for that item path."""
        item = self._make_item('mqtt.f')
        self.plugin.publish_topic('test/val', 99, item=item)
        self.assertIn(item.property.path, self.plugin._item_values)
