"""
tests.plugin_contract.base — Tier 1 contract tests for every SmartPlugin subclass.

These tests require no plugin.yaml and no knowledge of plugin internals.
They verify the invariants that every conforming plugin must satisfy purely
by virtue of inheriting from SmartPlugin.

Usage::

    from tests.plugin_contract.base import BasePluginContractTest
    from plugins.myplugin import MyPlugin

    class TestMyPlugin(BasePluginContractTest):
        PLUGIN_CLASS       = MyPlugin
        PLUGIN_INIT_PARAMS = {'host': '127.0.0.1', 'port': 502}

Class attributes
----------------
PLUGIN_CLASS : type
    The plugin class under test.  Must be set by the subclass.
PLUGIN_INIT_PARAMS : dict
    Keyword arguments passed to the plugin's __init__ and stored in
    _parameters (mirrors what lib.plugin normally does).
    Defaults to {}.
"""

import inspect
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import tests.common as common
common.register_shng_log_levels()

from tests.mock.core import MockSmartHome
from tests.plugin_contract._mockitem import MockItem
from lib.model.smartplugin import SmartPlugin


# ---------------------------------------------------------------------------
# Helper: instantiate a plugin the way PluginWrapper normally would
# ---------------------------------------------------------------------------

def make_plugin_instance(plugin_class, sh, init_params: dict | None = None):
    """
    Create a plugin instance with the loader-set attributes that PluginWrapper
    normally injects (``_sh``, ``_shortname``, ``_classname``, ``_configname``,
    ``_plugin_dir``, ``_parameters``).

    The function sets ``_sh`` and ``_parameters`` as *class* attributes before
    calling ``__init__`` (some plugins read them during init), then immediately
    promotes them to instance attributes via the official setter methods.

    Parameters
    ----------
    plugin_class : type
        SmartPlugin subclass to instantiate.
    sh : MockSmartHome
        The mock smarthome runtime.
    init_params : dict, optional
        Parameters forwarded both as ``**kwargs`` to ``__init__`` and stored in
        ``_parameters`` (what lib.metadata normally resolves).

    Returns
    -------
    SmartPlugin instance, or None if instantiation raised an exception.
    """
    if init_params is None:
        init_params = {}

    plugin_dir = os.path.dirname(os.path.abspath(inspect.getfile(plugin_class)))

    # Temporarily set class-level attributes that some plugins read during __init__.
    # Instance setters overwrite these immediately after.
    plugin_class._sh = sh
    plugin_class._parameters = dict(init_params)
    plugin_class._plugin_dir = plugin_dir

    # SmartDevicePlugin._set_item_attributes() reads self.metadata.itemdefinitions
    # which lib.plugin normally injects at load time.  Provide a stub so SDP
    # subclasses can be instantiated without a full plugin-loader run.
    try:
        from lib.model.smartdeviceplugin import SmartDevicePlugin as _SDP
        if issubclass(plugin_class, _SDP):
            # _classpath — module path used by SmartDevicePlugin.__init__ to derive
            # plugin_path; lib.plugin normally sets this before calling __init__
            if not hasattr(plugin_class, '_classpath'):
                plugin_class._classpath = plugin_class.__module__
            # metadata.itemdefinitions — normally injected by lib.plugin at load time.
            # Load item attribute names from plugin.yaml so _set_item_attributes()
            # can build the _item_attrs mapping (e.g. ITEM_ATTR_COMMAND → 'ex_command').
            if not hasattr(plugin_class, 'metadata'):
                from unittest.mock import MagicMock as _MagicMock
                import lib.shyaml as _shyaml
                _yaml_path = os.path.join(plugin_dir, 'plugin.yaml')
                _yaml = _shyaml.yaml_load(_yaml_path, ordered=False) or {} if os.path.isfile(_yaml_path) else {}
                _item_attr_keys = list((_yaml.get('item_attributes', {}) or {}).keys())
                _meta = _MagicMock()
                _meta.itemdefinitions = {k: {} for k in _item_attr_keys}
                plugin_class.metadata = _meta
    except ImportError:
        pass

    # Detect whether __init__ takes 'sh' as its first positional parameter.
    # SmartPlugin.__init__ uses **kwargs only; SmartDevicePlugin and most
    # "classic" plugin authors write def __init__(self, sh, *args, **kwargs).
    _params = list(inspect.signature(plugin_class.__init__).parameters.keys())
    _has_sh = len(_params) >= 2 and _params[1] == 'sh'

    try:
        plugin = plugin_class(sh, **init_params) if _has_sh else plugin_class(**init_params)
    except Exception:
        raise

    # Now promote to instance attributes via the official SmartPlugin API.
    # Derive shortname from module: 'plugins.myplugin' → 'myplugin'
    mod_parts = plugin_class.__module__.split('.')
    shortname = mod_parts[1] if len(mod_parts) >= 2 and mod_parts[0] == 'plugins' else plugin_class.__name__.lower()

    plugin._set_shortname(shortname)
    plugin._set_classname(plugin_class.__name__)
    plugin._set_configname(plugin_class.__name__.lower())
    plugin._set_sh(sh)
    plugin._set_plugin_dir(plugin_dir)

    return plugin


# ---------------------------------------------------------------------------
# Base contract test class
# ---------------------------------------------------------------------------

class BasePluginContractTest(unittest.TestCase):
    """Mix-in: Tier 1 contract tests for any SmartPlugin subclass."""

    PLUGIN_CLASS: type | None = None
    PLUGIN_INIT_PARAMS: dict = {}

    # -----------------------------------------------------------------------
    # Setup / teardown
    # -----------------------------------------------------------------------

    def setUp(self):
        # Call super first so that other setUp methods further down the MRO
        # (e.g. MqttPluginContractTest, SdpPluginContractTest) get a chance to
        # run their pre-requisite setup (patches, conn_type injection) before
        # we instantiate the plugin.
        super().setUp()
        if self.PLUGIN_CLASS is None:
            self.skipTest('PLUGIN_CLASS not set — this is the abstract base, not a real test run')
        # Only create sh/plugin if a lower-priority setUp has not already done so.
        # (SdpPluginContractTest and MqttPluginContractTest create them with extra
        # configuration and store them in self.sh / self.plugin before returning
        # from their own super().setUp() call.)
        if not hasattr(self, 'sh'):
            self.sh = MockSmartHome()
        if not hasattr(self, 'plugin'):
            self.plugin = make_plugin_instance(self.PLUGIN_CLASS, self.sh, self.PLUGIN_INIT_PARAMS)

    def tearDown(self):
        if hasattr(self, 'plugin') and self.plugin is not None:
            if getattr(self.plugin, 'alive', False):
                try:
                    self.plugin.stop()
                except Exception:
                    pass
        super().tearDown()

    def _make_item(self, path: str = 'contract.test', conf: dict | None = None) -> MockItem:
        return MockItem(path, conf)

    # -----------------------------------------------------------------------
    # Class-level contract
    # -----------------------------------------------------------------------

    def test_plugin_version_is_defined(self):
        """PLUGIN_VERSION must be a non-empty string."""
        v = getattr(self.PLUGIN_CLASS, 'PLUGIN_VERSION', None)
        self.assertIsNotNone(v, 'PLUGIN_VERSION is not defined')
        self.assertIsInstance(v, str, 'PLUGIN_VERSION must be a str')
        self.assertTrue(v.strip(), 'PLUGIN_VERSION must not be empty')

    def test_plugin_version_format(self):
        """PLUGIN_VERSION should follow x.y.z semver pattern."""
        v = getattr(self.PLUGIN_CLASS, 'PLUGIN_VERSION', '')
        self.assertRegex(
            v, r'^\d+\.\d+\.\d+',
            f'PLUGIN_VERSION {v!r} does not start with a x.y.z version number'
        )

    def test_allow_multiinstance_is_defined(self):
        """ALLOW_MULTIINSTANCE must be True or False, not None."""
        ami = getattr(self.PLUGIN_CLASS, 'ALLOW_MULTIINSTANCE', 'NOT_SET')
        self.assertIn(
            ami, (True, False),
            f'ALLOW_MULTIINSTANCE is {ami!r}; must be True or False'
        )

    def test_inherits_from_smartplugin(self):
        """Plugin class must inherit from SmartPlugin."""
        self.assertTrue(
            issubclass(self.PLUGIN_CLASS, SmartPlugin),
            f'{self.PLUGIN_CLASS.__name__} does not inherit from SmartPlugin'
        )

    def test_run_method_is_overridden(self):
        """run() must be overridden — SmartPlugin.run() raises NotImplementedError."""
        self.assertNotEqual(
            self.PLUGIN_CLASS.run, SmartPlugin.run,
            f'{self.PLUGIN_CLASS.__name__} does not override run()'
        )

    def test_stop_method_is_overridden(self):
        """stop() must be overridden — SmartPlugin.stop() raises NotImplementedError."""
        self.assertNotEqual(
            self.PLUGIN_CLASS.stop, SmartPlugin.stop,
            f'{self.PLUGIN_CLASS.__name__} does not override stop()'
        )

    # -----------------------------------------------------------------------
    # Post-__init__ state
    # -----------------------------------------------------------------------

    def test_alive_false_after_init(self):
        """alive must be False directly after __init__."""
        self.assertFalse(
            self.plugin.alive,
            'alive must be False after __init__; set it to True only inside run()'
        )

    def test_plg_item_dict_empty_after_init(self):
        """_plg_item_dict must be an empty dict after __init__."""
        self.assertEqual(self.plugin._plg_item_dict, {})

    def test_item_lookup_dict_empty_after_init(self):
        """_item_lookup_dict must be an empty dict after __init__."""
        self.assertEqual(self.plugin._item_lookup_dict, {})

    def test_get_item_list_empty_after_init(self):
        """get_item_list() must return [] after __init__."""
        self.assertEqual(self.plugin.get_item_list(), [])

    def test_get_trigger_items_empty_after_init(self):
        """get_trigger_items() must return [] after __init__."""
        self.assertEqual(self.plugin.get_trigger_items(), [])

    def test_get_mappings_empty_after_init(self):
        """get_mappings() must return [] after __init__."""
        self.assertEqual(self.plugin.get_mappings(), [])

    # -----------------------------------------------------------------------
    # Item registry contract
    # -----------------------------------------------------------------------

    def test_add_item_returns_true(self):
        """add_item() returns True when adding a new item."""
        item = self._make_item('reg.a')
        result = self.plugin.add_item(item)
        self.assertTrue(result)

    def test_add_item_appears_in_get_item_list(self):
        """After add_item(), item appears in get_item_list()."""
        item = self._make_item('reg.b')
        self.plugin.add_item(item)
        self.assertIn(item, self.plugin.get_item_list())

    def test_add_item_duplicate_returns_false(self):
        """Adding the same item twice returns False on the second call."""
        item = self._make_item('reg.c')
        self.plugin.add_item(item)
        result = self.plugin.add_item(item)
        self.assertFalse(result)

    def test_remove_item_returns_true(self):
        """remove_item() returns True for a registered item."""
        item = self._make_item('reg.d')
        self.plugin.add_item(item)
        result = self.plugin.remove_item(item)
        self.assertTrue(result)

    def test_remove_item_no_longer_in_list(self):
        """After remove_item(), item no longer in get_item_list()."""
        item = self._make_item('reg.e')
        self.plugin.add_item(item)
        self.plugin.remove_item(item)
        self.assertNotIn(item, self.plugin.get_item_list())

    def test_remove_item_not_registered_returns_false(self):
        """remove_item() returns False for an item that was never added."""
        item = self._make_item('reg.f')
        result = self.plugin.remove_item(item)
        self.assertFalse(result)

    def test_add_item_with_mapping_appears_in_lookup(self):
        """add_item(item, mapping='foo') → item in get_items_for_mapping('foo')."""
        item = self._make_item('reg.g')
        self.plugin.add_item(item, mapping='foo')
        self.assertIn(item, self.plugin.get_items_for_mapping('foo'))

    def test_add_item_with_mapping_listed_in_get_mappings(self):
        """Mapping key appears in get_mappings() after add_item with that mapping."""
        item = self._make_item('reg.h')
        self.plugin.add_item(item, mapping='bar')
        self.assertIn('bar', self.plugin.get_mappings())

    def test_add_item_as_updating_appears_in_trigger_items(self):
        """add_item(item, updating=True) → item in get_trigger_items()."""
        item = self._make_item('reg.i')
        self.plugin.add_item(item, updating=True)
        self.assertIn(item, self.plugin.get_trigger_items())

    def test_add_item_not_updating_not_in_trigger_items(self):
        """add_item(item) without updating=True → item NOT in get_trigger_items()."""
        item = self._make_item('reg.j')
        self.plugin.add_item(item, updating=False)
        self.assertNotIn(item, self.plugin.get_trigger_items())

    def test_register_updating_promotes_item(self):
        """register_updating() promotes a non-updating item to get_trigger_items()."""
        item = self._make_item('reg.k')
        self.plugin.add_item(item, updating=False)
        self.plugin.register_updating(item)
        self.assertIn(item, self.plugin.get_trigger_items())

    def test_different_items_are_independent(self):
        """Two items registered under different paths are stored independently."""
        a = self._make_item('reg.x')
        b = self._make_item('reg.y')
        self.plugin.add_item(a)
        self.plugin.add_item(b)
        self.assertEqual(len(self.plugin.get_item_list()), 2)

    # -----------------------------------------------------------------------
    # parse_item contract
    # -----------------------------------------------------------------------

    def test_parse_item_unknown_attrs_does_not_raise(self):
        """parse_item() with an item carrying no plugin attributes must not raise."""
        item = self._make_item('parse.a', conf={})
        try:
            self.plugin.parse_item(item)
        except Exception as exc:
            self.fail(f'parse_item() raised unexpectedly: {exc}')

    def test_parse_item_return_is_callable_or_none(self):
        """If parse_item() returns a value, it must be callable (a method reference)."""
        item = self._make_item('parse.b', conf={})
        result = self.plugin.parse_item(item)
        if result is not None:
            self.assertTrue(callable(result), f'parse_item() returned non-callable {result!r}')

    # -----------------------------------------------------------------------
    # update_item when stopped
    # -----------------------------------------------------------------------

    def test_update_item_when_stopped_does_not_raise(self):
        """update_item() when alive=False must not raise (base class logs and returns)."""
        item = self._make_item('upd.a')
        self.plugin.add_item(item)
        self.assertFalse(self.plugin.alive)
        try:
            self.plugin.update_item(item, caller='test', source=None, dest=None)
        except Exception as exc:
            self.fail(f'update_item() raised while plugin is stopped: {exc}')

    # -----------------------------------------------------------------------
    # deinit contract
    # -----------------------------------------------------------------------

    def test_deinit_empties_item_registry(self):
        """deinit() must unregister all items."""
        for i in range(3):
            self.plugin.add_item(self._make_item(f'deinit.{i}'))
        self.assertEqual(len(self.plugin.get_item_list()), 3)
        self.plugin.deinit()
        self.assertEqual(self.plugin.get_item_list(), [])

    def test_deinit_calls_stop_if_alive(self):
        """deinit() must call stop() if the plugin is alive."""
        # Mark alive manually to avoid needing a real run()
        self.plugin.alive = True
        stopped = []
        original_stop = self.plugin.stop

        def _stop():
            stopped.append(True)
            self.plugin.alive = False

        self.plugin.stop = _stop
        self.plugin.deinit()
        self.assertTrue(stopped, 'deinit() did not call stop() while plugin was alive')
        self.plugin.stop = original_stop

    # -----------------------------------------------------------------------
    # Pause item
    # -----------------------------------------------------------------------

    def test_pause_item_none_initially(self):
        """_pause_item must be None after __init__."""
        self.assertIsNone(self.plugin._pause_item)

    def test_pause_item_registered_via_parse_item(self):
        """An item whose path matches _pause_item_path is registered as the pause item."""
        self.plugin._pause_item_path = 'pause.ctrl'
        item = self._make_item('pause.ctrl')
        self.plugin.parse_item(item)
        self.assertIs(self.plugin._pause_item, item)
