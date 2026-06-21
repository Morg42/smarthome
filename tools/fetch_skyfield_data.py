#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  This file is part of SmartHomeNG
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

"""
Ensures the skyfield ephemeris file (de421.bsp, ~17MB) used by the optional
skyfield backend of lib.orb is present on disk, downloading it once if
missing.

This is the only network access the skyfield backend ever requires: de421.bsp
covers 1899-07-28 through 2053-10-08 and never needs re-fetching within that
range. Run this once before switching lib.orb to the skyfield backend (set
``orb_backend: skyfield`` in etc/smarthome.yaml) so SmartHomeNG's normal
runtime never needs network access for it - matches the existing
skyfield.api.Loader behaviour of skipping the download entirely if the file
already exists at the target path, so re-running this script is always safe
and a no-op once the file is in place.

Not run automatically at startup/install time: doing so unconditionally would
download 17MB for every installation regardless of which backend is actually
configured (orb_backend defaults to 'ephem'), reintroducing exactly the kind
of required network access this is meant to avoid for everyone who hasn't
opted into skyfield.

Usage:
    tools/fetch_skyfield_data.py
"""

import os
import sys

sh_basedir = os.sep.join(os.path.realpath(__file__).split(os.sep)[:-2])
sys.path.insert(0, sh_basedir)

try:
    from lib.orb import _BACKENDS, _SkyfieldBackend
except ImportError as e:
    print("Could not import lib.orb - is SmartHomeNG's venv active? ({})".format(e))
    sys.exit(1)

if 'skyfield' not in _BACKENDS:
    print("lib.orb's skyfield backend is not available (skyfield not installed).")
    print("Run 'pip install -r requirements/base.txt' first, then re-run this script.")
    sys.exit(1)

data_dir = _SkyfieldBackend._data_dir()
target = os.path.join(data_dir, 'de421.bsp')

if os.path.exists(target):
    print(f'Skyfield ephemeris data already present at {target} - nothing to do.')
    sys.exit(0)

print(f'Fetching skyfield ephemeris data (de421.bsp, ~17MB) to {data_dir} ...', flush=True)
print('This is a one-time download - the file is valid through 2053 and will not be re-fetched.', flush=True)

try:
    _SkyfieldBackend._ensure_loaded()
except Exception as e:
    print(f'ERROR: could not download skyfield ephemeris data: {e}')
    sys.exit(1)

print(f'Done. Skyfield ephemeris data is now cached at {target}.')
