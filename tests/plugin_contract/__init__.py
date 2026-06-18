"""
tests.plugin_contract — reusable contract-test mix-ins for SmartHomeNG plugins.

Each tier is an independent mix-in; combine as needed:

    from tests.plugin_contract.base      import BasePluginContractTest
    from tests.plugin_contract.with_yaml import YamlPluginContractTest
    from tests.plugin_contract.mqtt      import MqttPluginContractTest
    from tests.plugin_contract.sdp       import SdpPluginContractTest

Minimal usage (SmartPlugin subclass, no plugin.yaml):

    class TestMyPlugin(BasePluginContractTest):
        PLUGIN_CLASS      = MyPlugin
        PLUGIN_INIT_PARAMS = {'host': '127.0.0.1'}

With plugin.yaml validation and item-attribute tests:

    class TestMyPlugin(BasePluginContractTest, YamlPluginContractTest):
        PLUGIN_CLASS      = MyPlugin
        PLUGIN_INIT_PARAMS = {'host': '127.0.0.1'}
        # optional — provide if the plugin requires attribute combinations:
        ITEM_ATTR_SETS    = [
            {'my_command': 'Device.Power', 'my_write': True},
            {'my_command': 'Device.Temp',  'my_read':  True},
        ]

See each module for full documentation.
"""
