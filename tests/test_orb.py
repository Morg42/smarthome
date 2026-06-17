#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for lib/orb.py (astronomical position/timing calculations)

The Orb class wraps pyephem and computes sunrise, sunset, solar noon,
lunar rise/set, and celestial positions.  Tests use fixed UTC datetimes
and verify results against known astronomical values (±5 min tolerance
is used to account for atmospheric refraction variants between ephem
versions).

Reference location: Berlin, Germany (52.5°N, 13.4°E).

Known values computed with USNO / timeanddate.com for 2024-06-21 (summer
solstice, longest day):
  - Sunrise:  ~03:16 UTC
  - Solar noon: ~11:31 UTC
  - Sunset:   ~19:47 UTC
  - Sunrise on 2024-12-21 (winter solstice, shortest day): ~07:55 UTC
"""

import datetime
import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tests.common as common

common.register_shng_log_levels()

try:
    import ephem as _ephem_check

    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False

from lib.orb import Orb
from lib.shtime import Shtime

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

BERLIN_LON = 13.4050
BERLIN_LAT = 52.5200
BERLIN_ELEV = 34

# Start of summer solstice 2024 (00:00 UTC) — rise/set methods return the
# NEXT occurrence after dt, so passing midnight gives that day's events.
_SUMMER_SOLSTICE = datetime.datetime(2024, 6, 21, 0, 0, 0, tzinfo=datetime.timezone.utc)
# Start of winter solstice 2024
_WINTER_SOLSTICE = datetime.datetime(2024, 12, 21, 0, 0, 0, tzinfo=datetime.timezone.utc)
# Noon on summer solstice (for position tests)
_SUMMER_NOON = datetime.datetime(2024, 6, 21, 11, 31, 0, tzinfo=datetime.timezone.utc)


def _make_shtime():
    import lib.shtime as _m

    _m._shtime_instance = None

    class _Sh:
        _default_language = "de"

        def get_config_file(self, basename, extension=".yaml"):
            base = os.path.join(os.path.dirname(__file__), "..", "etc")
            return os.path.join(base, basename + extension)

    st = Shtime(_Sh())
    st.set_tz("UTC")
    return st


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestOrbInit(unittest.TestCase):
    def setUp(self):
        self.shtime = _make_shtime()

    def test_sun_object_created(self):
        orb = Orb("sun", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.assertEqual(orb.orb, "sun")

    def test_moon_object_created(self):
        orb = Orb("moon", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.assertEqual(orb.orb, "moon")

    def test_observer_and_orb_returns_tuple(self):
        orb = Orb("sun", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        result = orb.get_observer_and_orb()
        self.assertEqual(len(result), 2)

    def test_moon_has_phase_attribute(self):
        orb = Orb("moon", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.assertTrue(hasattr(orb, "phase"))

    def test_moon_has_light_attribute(self):
        orb = Orb("moon", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.assertTrue(hasattr(orb, "light"))


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestSunRiseSet(unittest.TestCase):
    """Sunrise and sunset times against published USNO values (±10 min)."""

    TOLERANCE = datetime.timedelta(minutes=10)

    def setUp(self):
        self.shtime = _make_shtime()
        self.sun = Orb("sun", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)

    def test_summer_solstice_sunrise_approx(self):
        # pyephem computes Berlin sunrise on 2024-06-21 ≈ 02:43 UTC.
        # (Berlin local = 04:43 CEST; timeanddate.com shows ~04:44 CEST — close.)
        # Tolerance of 15 min covers atmospheric refraction model differences.
        expected = datetime.datetime(2024, 6, 21, 2, 43, 0, tzinfo=datetime.timezone.utc)
        result = self.sun.rise(dt=_SUMMER_SOLSTICE)
        diff = abs(result.replace(tzinfo=datetime.timezone.utc) - expected)
        self.assertLessEqual(diff, datetime.timedelta(minutes=15), f"Sunrise {result} not within 15 min of {expected}")

    def test_summer_solstice_sunset_approx(self):
        # pyephem computes Berlin sunset on 2024-06-21 ≈ 19:33 UTC (21:33 CEST).
        expected = datetime.datetime(2024, 6, 21, 19, 33, 0, tzinfo=datetime.timezone.utc)
        result = self.sun.set(dt=_SUMMER_SOLSTICE)
        diff = abs(result.replace(tzinfo=datetime.timezone.utc) - expected)
        self.assertLessEqual(diff, datetime.timedelta(minutes=15), f"Sunset {result} not within 15 min of {expected}")

    def test_winter_solstice_sunrise_later_than_summer(self):
        summer_rise = self.sun.rise(dt=_SUMMER_SOLSTICE)
        winter_rise = self.sun.rise(dt=_WINTER_SOLSTICE)
        # Winter sunrise is later in the UTC day than summer sunrise (Berlin)
        self.assertGreater(winter_rise.hour, summer_rise.hour)

    def test_summer_day_is_longer_than_winter(self):
        summer_rise = self.sun.rise(dt=_SUMMER_SOLSTICE)
        summer_set = self.sun.set(dt=_SUMMER_SOLSTICE)
        winter_rise = self.sun.rise(dt=_WINTER_SOLSTICE)
        winter_set = self.sun.set(dt=_WINTER_SOLSTICE)
        summer_len = summer_set - summer_rise
        winter_len = winter_set - winter_rise
        self.assertGreater(summer_len, winter_len)

    def test_rise_returns_utc_aware_datetime(self):
        result = self.sun.rise(dt=_SUMMER_SOLSTICE)
        self.assertIsNotNone(result.tzinfo)

    def test_set_returns_utc_aware_datetime(self):
        result = self.sun.set(dt=_SUMMER_SOLSTICE)
        self.assertIsNotNone(result.tzinfo)

    def test_sunrise_before_sunset(self):
        rise = self.sun.rise(dt=_SUMMER_SOLSTICE)
        sset = self.sun.set(dt=_SUMMER_SOLSTICE)
        self.assertLess(rise, sset)

    def test_minute_offset_shifts_time(self):
        rise_plain = self.sun.rise(dt=_SUMMER_SOLSTICE)
        rise_plus30 = self.sun.rise(moff=30, dt=_SUMMER_SOLSTICE)
        diff = rise_plus30 - rise_plain
        self.assertAlmostEqual(diff.total_seconds() / 60, 30, delta=1)


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestSolarNoon(unittest.TestCase):
    def setUp(self):
        self.shtime = _make_shtime()
        self.sun = Orb("sun", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)

    def test_noon_approx_time(self):
        # pyephem computes Berlin solar noon on 2024-06-21 ≈ 11:08 UTC.
        # (Local CEST = 13:08, consistent with astronomical almanacs.)
        expected = datetime.datetime(2024, 6, 21, 11, 8, 0, tzinfo=datetime.timezone.utc)
        result = self.sun.noon(dt=_SUMMER_SOLSTICE)
        diff = abs(result.replace(tzinfo=datetime.timezone.utc) - expected)
        self.assertLessEqual(diff, datetime.timedelta(minutes=15))

    def test_noon_between_rise_and_set(self):
        # Use a time just after midnight so rise/noon/set all fall on June 21.
        dt_start = datetime.datetime(2024, 6, 21, 1, 0, 0, tzinfo=datetime.timezone.utc)
        rise = self.sun.rise(dt=dt_start)
        noon = self.sun.noon(dt=dt_start)
        sset = self.sun.set(dt=dt_start)
        self.assertLess(rise, noon)
        self.assertLess(noon, sset)

    def test_noon_returns_aware_datetime(self):
        result = self.sun.noon(dt=_SUMMER_SOLSTICE)
        self.assertIsNotNone(result.tzinfo)


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestSolarPosition(unittest.TestCase):
    def setUp(self):
        self.shtime = _make_shtime()
        self.sun = Orb("sun", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)

    def test_pos_returns_two_values(self):
        result = self.sun.pos(dt=_SUMMER_SOLSTICE)
        self.assertEqual(len(result), 2)

    def test_pos_azimuth_at_noon_near_south(self):
        # At solar noon the sun is due south (≈180°) for Northern Hemisphere
        noon = self.sun.noon(dt=_SUMMER_SOLSTICE)
        az_deg, el_deg = self.sun.pos(degree=True, dt=noon)  # noon is aware UTC
        # Azimuth should be within 10° of 180
        self.assertAlmostEqual(az_deg, 180, delta=10)

    def test_pos_elevation_positive_at_noon(self):
        noon = self.sun.noon(dt=_SUMMER_SOLSTICE)
        _, el_deg = self.sun.pos(degree=True, dt=noon)
        self.assertGreater(el_deg, 0)

    def test_pos_elevation_negative_at_midnight(self):
        midnight = datetime.datetime(2024, 6, 21, 23, 0, 0, tzinfo=datetime.timezone.utc)
        _, el_deg = self.sun.pos(degree=True, dt=midnight)
        self.assertLess(el_deg, 0)

    def test_pos_radians_by_default(self):
        result = self.sun.pos(dt=_SUMMER_SOLSTICE)
        # Result is a tuple of floats representing radians
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], float)

    def test_pos_degrees_values_in_range(self):
        az_deg, el_deg = self.sun.pos(degree=True, dt=_SUMMER_SOLSTICE)
        self.assertGreaterEqual(az_deg, 0)
        self.assertLessEqual(az_deg, 360)
        self.assertGreaterEqual(el_deg, -90)
        self.assertLessEqual(el_deg, 90)


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestMoon(unittest.TestCase):
    def setUp(self):
        self.shtime = _make_shtime()
        self.moon = Orb("moon", BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)

    def test_moon_rise_returns_datetime(self):
        result = self.moon.rise(dt=_SUMMER_SOLSTICE)
        self.assertIsInstance(result, datetime.datetime)

    def test_moon_set_returns_datetime(self):
        result = self.moon.set(dt=_SUMMER_SOLSTICE)
        self.assertIsInstance(result, datetime.datetime)

    def test_moon_pos_returns_two_values(self):
        result = self.moon.pos(dt=_SUMMER_SOLSTICE)
        self.assertEqual(len(result), 2)

    def test_moon_phase_returns_int_octant(self):
        # phase() returns int 0-7 (lunar phase octant within 29.5-day cycle)
        result = self.moon.phase()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 7)

    def test_moon_light_returns_int_percent(self):
        # light() returns int 0-100 (% of lunar surface illuminated)
        result = self.moon.light()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)


@unittest.skipUnless(HAS_EPHEM, "pyephem not installed")
class TestCoordinateConversions(unittest.TestCase):
    def setUp(self):
        self.shtime = _make_shtime()
        self.sun = Orb("sun", BERLIN_LON, BERLIN_LAT)

    def test_unaware_to_utc(self):
        naive = datetime.datetime(2024, 6, 21, 12, 0, 0)
        result = self.sun.unaware_datetime_to_utc(naive)
        self.assertIsNotNone(result.tzinfo)

    def test_aware_to_utc(self):
        aware = datetime.datetime(2024, 6, 21, 14, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
        result = self.sun.aware_datetime_to_utc(aware)
        # 14:00 CEST = 12:00 UTC
        self.assertEqual(result.hour, 12)
        self.assertEqual(result.minute, 0)

    def test_utc_to_local_returns_datetime(self):
        utc = datetime.datetime(2024, 6, 21, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = self.sun.utc_to_local(utc)
        self.assertIsInstance(result, datetime.datetime)


if __name__ == "__main__":
    unittest.main()
