"""
Lightweight mock item for plugin contract tests.

A real lib.item.item.Item requires a full SmartHomeNG runtime.  For contract
tests we only need the surface that SmartPlugin touches:

    item.property.path      — str path, used as dict key
    item.conf               — dict of item-level plugin attributes
    item()                  — callable: get/set current value
    item.type()             — returns item type string
    item.remove_method_trigger(fn) — called by SmartPlugin.unparse_item()
    item.add_method_trigger(fn)    — called implicitly during parse_item
    item.last_update()      — returns a datetime (used by MqttPlugin)
    item.last_change()      — returns a datetime
"""

import datetime


class _MockProperty:
    def __init__(self, path: str) -> None:
        self.path = path
        self.type = 'foo'   # item data type; plugins may read item.property.type


class MockItem:
    """
    Minimal stand-in for lib.item.item.Item.

    Usage::

        item = MockItem('lights.living', conf={'my_command': 'Light.Power', 'my_write': True})
        plugin.parse_item(item)
    """

    def __init__(self, path: str = 'test.item', conf: dict | None = None) -> None:
        self.property = _MockProperty(path)
        # Some plugin base classes (e.g. SmartDevicePlugin) access item.path directly
        # rather than item.property.path.  Keep both in sync.
        self.path = path
        self.conf = conf if conf is not None else {}
        self._value = None
        self._method_triggers: list = []

    # ------------------------------------------------------------------
    # callable interface: item() → get value, item(v) → set value
    # ------------------------------------------------------------------
    def __call__(self, value=None, caller=None, source=None, dest=None):
        if value is not None:
            self._value = value
            for fn in list(self._method_triggers):
                try:
                    fn(self, caller, source, dest)
                except Exception:
                    pass
        return self._value

    # ------------------------------------------------------------------
    # type (SmartPlugin.update_item uses item.type() in some plugins)
    # ------------------------------------------------------------------
    def type(self) -> str:
        return 'foo'

    # ------------------------------------------------------------------
    # method-trigger registration (called by SmartPlugin internals)
    # ------------------------------------------------------------------
    def add_method_trigger(self, fn) -> None:
        if fn not in self._method_triggers:
            self._method_triggers.append(fn)

    def remove_method_trigger(self, fn) -> None:
        if fn in self._method_triggers:
            self._method_triggers.remove(fn)
        else:
            raise ValueError(fn)

    # ------------------------------------------------------------------
    # timestamp helpers (used by MqttPlugin._update_item_values)
    # ------------------------------------------------------------------
    def last_update(self) -> datetime.datetime:
        return datetime.datetime.now()

    def last_change(self) -> datetime.datetime:
        return datetime.datetime.now()

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return f'MockItem({self.property.path!r})'
