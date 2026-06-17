import logging
import os
import sys
import pathlib

# with Linux standard installation of SmartHomeNG
# realpath of __file__ will be '/usr/local/smarthome/tests/common.py'
# so BASE becomes '/usr/local/smarthome'
if os.name != "nt":
    BASE = "/".join(os.path.realpath(__file__).split("/")[:-2])
else:
    BASE = str(pathlib.Path(__file__).resolve().parents[1])
sys.path.insert(0, BASE)


def register_shng_log_levels():
    """Register SmartHomeNG custom log levels if not already present.

    SmartHomeNG defines several levels beyond the standard Python set.
    This helper is idempotent — safe to call multiple times or from
    multiple test modules.
    """
    _levels = [
        (31, "NOTICE"),
        (13, "DBGHIGH"),
        (12, "DBGMED"),
        (11, "DBGLOW"),
        (9, "DEVELOP"),
    ]
    for level, name in _levels:
        if not hasattr(logging.getLoggerClass(), name.lower()):

            def _make_method(lvl):
                def _method(self, msg, *args, **kwargs):
                    if self.isEnabledFor(lvl):
                        self._log(lvl, msg, args, **kwargs)

                return _method

            logging.addLevelName(level, name)
            setattr(logging, name, level)
            setattr(logging.getLoggerClass(), name.lower(), _make_method(level))
