#!/usr/bin/env python3
#
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2011-2014 Marcus Popp                          marcus@popp.mx
# Copyright 2021-2025 Bernd Meiners                 Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
##########################################################################

import logging
import datetime
import math
import os
import dateutil.relativedelta

from dateutil.tz import tzutc

from lib.shtime import Shtime

logger = logging.getLogger(__name__)

try:
    import ephem
except ImportError:
    ephem = None  # noqa

try:
    from skyfield.api import Loader, wgs84
    from skyfield import almanac as skyfield_almanac
except ImportError:
    Loader = None  # noqa
    wgs84 = None  # noqa
    skyfield_almanac = None  # noqa


"""
This library contains a class Orb for calculating sun or moon related events.

The actual ephemeris computation is delegated to a swappable backend (see
_OrbBackend below) - currently only an ephem-based backend exists. This
indirection exists to allow evaluating alternative ephemeris libraries
(e.g. skyfield) without changing Orb's public API or any of its callers.
"""


class _OrbBackend:
    """
    Backend interface for astronomical calculations.

    All datetime/timezone normalisation, degree-offset clamping (avoiding
    NeverUp/AlwaysUp conditions for non-zero offsets) and moff/day-adjustment
    arithmetic lives in Orb itself, so it is identical across backends. A
    backend only has to answer "given this resolved UTC instant, body and
    horizon, when does the next transit/antitransit/rising/setting happen,
    or where is the body right now" - nothing more.

    next_rising()/next_setting() must return None (not raise) when the body
    does not cross the given horizon during the relevant circuit (midnight
    sun / polar night with doff=0, or an unreachable offset that slipped
    through despite clamping) - this is a backend-agnostic contract, not an
    ephem-specific exception type.
    """

    def get_observer_and_orb(self, lon, lat, elev, body):
        raise NotImplementedError

    def next_transit(self, lon, lat, elev, body, date_utc, doff):
        raise NotImplementedError

    def next_antitransit(self, lon, lat, elev, body, date_utc, doff):
        raise NotImplementedError

    def next_rising(self, lon, lat, elev, body, date_utc, doff, center):
        raise NotImplementedError

    def next_setting(self, lon, lat, elev, body, date_utc, doff, center):
        raise NotImplementedError

    def position(self, lon, lat, elev, body, date_utc):
        """Returns (azimuth_rad, altitude_rad)."""
        raise NotImplementedError

    def moon_light_percent(self, lon, lat, elev, date_utc):
        """Returns the illuminated fraction of the moon's disc, 0-100."""
        raise NotImplementedError

    def moon_phase_octant(self, lon, lat, elev, date_utc):
        """Returns the moon phase as an octant of its cycle, 0-7."""
        raise NotImplementedError


class _EphemBackend(_OrbBackend):
    """PyEphem-based implementation of _OrbBackend."""

    def get_observer_and_orb(self, lon, lat, elev, body):
        """
        Return a tuple of an instance of an observer with location information
        and a celestial body
        Both returned objects are uniquely created to prevent errors in computation

        See also this thread at `Stackoverflow <https://stackoverflow.com/questions/26428904/pyephem-advances-observer-date-on-neveruperror>`_
        dated back to 2015 where the creator of pyephem writes:

        > Second answer: As long as each thread has its own Moon and Observer objects,
          it should be able to do its own computations without ruining those of any other threads.

        :return: tuple of observer and celestial body
        """
        observer = ephem.Observer()
        # ephem expects lat and lon as strings
        observer.long = str(lon)
        observer.lat = str(lat)
        if elev:
            observer.elevation = float(elev)

        if body == 'sun':
            orb = ephem.Sun()
            logger.debug("'sun' object requested in function get_observer_and_orb()")
        elif body == 'moon':
            orb = ephem.Moon()
            logger.debug("'moon' object requested in function get_observer_and_orb()")
        else:
            logger.error("neither 'sun' nor 'moon' requested in function get_observer_and_orb()")

        return observer, orb

    def next_transit(self, lon, lat, elev, body, date_utc, doff):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, body)
        observer.date = date_utc
        observer.horizon = str(doff)
        return observer.next_transit(orb).datetime().replace(tzinfo=tzutc())

    def next_antitransit(self, lon, lat, elev, body, date_utc, doff):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, body)
        observer.date = date_utc
        observer.horizon = str(doff)
        return observer.next_antitransit(orb).datetime().replace(tzinfo=tzutc())

    def next_rising(self, lon, lat, elev, body, date_utc, doff, center):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, body)
        observer.date = date_utc
        observer.horizon = str(doff)
        try:
            if not doff == 0:
                next_rising = observer.next_rising(orb, use_center=center).datetime()
            else:
                next_rising = observer.next_rising(orb).datetime()
        except (ephem.AlwaysUpError, ephem.NeverUpError) as e:
            logger.notice(f'ephem: {body} has no rise event for {date_utc} at this location ({e}); returning None')
            return None
        return next_rising.replace(tzinfo=tzutc())

    def next_setting(self, lon, lat, elev, body, date_utc, doff, center):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, body)
        observer.date = date_utc
        observer.horizon = str(doff)
        try:
            if not doff == 0:
                next_setting = observer.next_setting(orb, use_center=center).datetime()
            else:
                next_setting = observer.next_setting(orb).datetime()
        except (ephem.AlwaysUpError, ephem.NeverUpError) as e:
            logger.notice(f'ephem: {body} has no set event for {date_utc} at this location ({e}); returning None')
            return None
        return next_setting.replace(tzinfo=tzutc())

    def position(self, lon, lat, elev, body, date_utc):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, body)
        observer.date = date_utc
        orb.compute(observer)
        return (orb.az, orb.alt)

    def moon_light_percent(self, lon, lat, elev, date_utc):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, 'moon')
        observer.date = date_utc
        orb.compute(observer)
        return int(round(orb.moon_phase * 100))

    def moon_phase_octant(self, lon, lat, elev, date_utc):
        observer, orb = self.get_observer_and_orb(lon, lat, elev, 'moon')
        observer.date = date_utc
        orb.compute(observer)
        cycle = 29.530588861
        last = ephem.previous_new_moon(observer.date)
        frac = (observer.date - last) / cycle
        return int(round(frac * 8))


class _SkyfieldBackend(_OrbBackend):
    """
    Skyfield-based implementation of _OrbBackend.

    Skyfield's almanac search functions (find_risings/find_settings/find_transits)
    sample the search window and bisect, unlike pyephem's Newton-iteration-based
    next_rising()/next_setting()/next_transit() - this is structurally more robust
    near turning points (e.g. close to a solstice, where the rate of change of
    sunset time approaches zero) where the iterative approach has been observed to
    occasionally overshoot. See orb_eph.py vs. orb_sky.py prototype comparison at
    https://github.com/CaeruleusAqua/smarthome_skyfield for the origin of this
    implementation's approach.

    Ephemeris data (de421.bsp, ~17MB) is downloaded on first use and cached on disk;
    requires network access the first time a Skyfield-backed Orb is created.
    """

    # Loaded lazily, shared across all instances/Orb objects in this process -
    # loading the ephemeris file and timescale data is expensive and the data
    # itself is stateless/reusable.
    _load = None
    _planets = None
    _ts = None

    @classmethod
    def _ensure_loaded(cls):
        if cls._planets is not None:
            return
        data_dir = cls._data_dir()
        cls._load = Loader(data_dir)
        cls._planets = cls._load('de421.bsp')
        cls._ts = cls._load.timescale()
        logger.info(f'skyfield: loaded de421.bsp ephemeris data from {data_dir}')

    @staticmethod
    def _data_dir():
        sh = getattr(Shtime.get_instance(), '_sh', None)
        var_dir = getattr(sh, '_var_dir', None)
        if var_dir:
            return os.path.join(var_dir, 'skyfield-data')
        return '~/.skyfield-data'

    def _body(self, body):
        self._ensure_loaded()
        return self._planets[body]

    def _observer(self, lon, lat, elev):
        self._ensure_loaded()
        topos = wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon, elevation_m=elev or 0)
        return self._planets['earth'] + topos

    def get_observer_and_orb(self, lon, lat, elev, body):
        return self._observer(lon, lat, elev), self._body(body)

    def next_transit(self, lon, lat, elev, body, date_utc, doff):
        # doff (degree offset for the horizon) only affects rise/set, not transit
        # (the meridian crossing happens regardless of horizon) - kept as a
        # parameter purely to match the shared _OrbBackend interface.
        observer = self._observer(lon, lat, elev)
        orb = self._body(body)
        t0 = self._ts.from_datetime(date_utc)
        t1 = self._ts.from_datetime(date_utc + datetime.timedelta(days=2))
        times = skyfield_almanac.find_transits(observer, orb, t0, t1)
        if len(times) == 0:
            return None
        return times[0].utc_datetime().replace(tzinfo=tzutc())

    def next_antitransit(self, lon, lat, elev, body, date_utc, doff):
        # skyfield has no public antitransit finder; almanac.find_transits() looks
        # for hour angle 0 (upper meridian crossing). almanac._find() is the
        # private generic search helper find_transits() itself uses - reuse it
        # directly with a target hour angle of pi (180°, lower meridian crossing).
        observer = self._observer(lon, lat, elev)
        orb = self._body(body)
        t0 = self._ts.from_datetime(date_utc)
        t1 = self._ts.from_datetime(date_utc + datetime.timedelta(days=2))

        def _antitransit_hour_angle(latitude, declination, altitude_radians):
            return math.pi

        times, _events = skyfield_almanac._find(observer, orb, t0, t1, 0, _antitransit_hour_angle)
        if len(times) == 0:
            return None
        return times[0].utc_datetime().replace(tzinfo=tzutc())

    def next_rising(self, lon, lat, elev, body, date_utc, doff, center):
        # center (use_center in the ephem backend) has no equivalent in skyfield's
        # find_risings()/find_settings(): skyfield always computes against the
        # body's actual apparent disc, there is no "upper limb" mode to opt out of.
        observer = self._observer(lon, lat, elev)
        orb = self._body(body)
        t0 = self._ts.from_datetime(date_utc)
        t1 = self._ts.from_datetime(date_utc + datetime.timedelta(days=2))
        times, events = skyfield_almanac.find_risings(observer, orb, t0, t1, doff)
        for time, event in zip(times, events):
            if event:
                return time.utc_datetime().replace(tzinfo=tzutc())
        # every candidate in the window was a "merely transits, doesn't touch
        # the horizon" entry - midnight sun / polar night for this horizon.
        logger.notice(f'skyfield: {body} has no rise event for {date_utc} at this location; returning None')
        return None

    def next_setting(self, lon, lat, elev, body, date_utc, doff, center):
        observer = self._observer(lon, lat, elev)
        orb = self._body(body)
        t0 = self._ts.from_datetime(date_utc)
        t1 = self._ts.from_datetime(date_utc + datetime.timedelta(days=2))
        times, events = skyfield_almanac.find_settings(observer, orb, t0, t1, doff)
        for time, event in zip(times, events):
            if event:
                return time.utc_datetime().replace(tzinfo=tzutc())
        logger.notice(f'skyfield: {body} has no set event for {date_utc} at this location; returning None')
        return None

    def position(self, lon, lat, elev, body, date_utc):
        observer = self._observer(lon, lat, elev)
        orb = self._body(body)
        t = self._ts.from_datetime(date_utc)
        alt, az, _distance = observer.at(t).observe(orb).apparent().altaz()
        return (az.radians, alt.radians)

    def moon_light_percent(self, lon, lat, elev, date_utc):
        self._ensure_loaded()
        t = self._ts.from_datetime(date_utc)
        phase_angle = skyfield_almanac.moon_phase(self._planets, t).radians
        light = (1 - math.cos(phase_angle)) / 2 * 100
        return int(round(light))

    def moon_phase_octant(self, lon, lat, elev, date_utc):
        self._ensure_loaded()
        t = self._ts.from_datetime(date_utc)
        phase_angle = skyfield_almanac.moon_phase(self._planets, t).degrees
        return int(round(phase_angle / 360 * 8))


_BACKENDS = {}
if ephem is not None:
    _BACKENDS['ephem'] = _EphemBackend
if Loader is not None:
    _BACKENDS['skyfield'] = _SkyfieldBackend


class Orb:
    """
    Save an observers location and the name of a celestial body for future use

    The Methods internally use a swappable backend for computation (currently
    only PyEphem is implemented, see _OrbBackend/_EphemBackend above).

    All calculations are based on utc time.
    Changelog of pypehem:
    > Version 4.1.1 (2021 November 27)
    > When you provide PyEphem with a Python datetime that has a time zone attached,
    > PyEphem now detects the time zone and converts the date and time to UTC automatically.

    To prevent side effects by this behaviour every datetime object given to any function in class Orb
    will be converted to utc.
    In case the given datetime is
    - naive (no timezone attached) --> the current timezone of SmartHomeNG will be used and the datetime will be converted to utc
    - has a timezone other than utc --> dt will be converted to utc
    - has utc timezone --> dt will not be changed and has always an offset of 0:00

    TODO:
    It can be that datetime conversion from and to utc is ambigous:
    Imagine October 27th, in 2024, at 2:30 in the night.
    dt = datetime(2024, 10, 27, 2, 30, tzinfo=berlin)
    This is ambigous because it could well be summertime having still utc+2 hours or wintertime with utc+1 hours
    This ambiguity is not handled right now
    """

    def __init__(self, orb, lon, lat, elev=False, neverup_delta=0.00001, backend='ephem'):
        """
        Save location and celestial body

        :param orb: either 'sun' or 'moon'
        :param lon: longitude of observer in degrees
        :param lat: latitude of observer in degrees
        :param elev: elevation of observer in meters
        :param backend: name of the ephemeris backend to use (currently only 'ephem')
        """
        try:
            self._backend = _BACKENDS[backend]()
        except KeyError:
            logger.warning(f"Could not find/use ephemeris backend '{backend}'!")
            return

        self.shtime = Shtime.get_instance()

        self.orb = orb
        if orb != 'sun' and orb != 'moon':
            logger.error("neither 'sun' nor 'moon' given as parameter for creation of Orb object")

        self.lat = lat
        self.lon = lon
        self.elev = elev
        self.neverup_delta = None

        if self.orb == 'sun':
            self.neverup_delta = neverup_delta
            if not neverup_delta == 0.00001:
                logger.notice(f'neverup_delta was adjusted to {neverup_delta} for sun calculations')
        elif self.orb == 'moon':
            self.phase = self._phase
            self.light = self._light

        logger.debug(f'Orb object {orb=} created with location {lon=},{lat=},{elev=}, {backend=}')

    def get_observer_and_orb(self):
        """
        Return a tuple of an instance of an observer with location information
        and a celestial body, as provided by the active backend. Both returned
        objects are uniquely created to prevent errors in computation.

        :return: tuple of observer and celestial body
        """
        return self._backend.get_observer_and_orb(self.lon, self.lat, self.elev, self.orb)

    def unaware_datetime_to_utc(self, naive_dt):
        local_aware = naive_dt.replace(tzinfo=self.shtime.tzinfo())
        return local_aware.astimezone(datetime.timezone.utc)

    def aware_datetime_to_utc(self, aware_dt):
        return aware_dt.astimezone(datetime.timezone.utc)

    def utc_to_local(self, utc_dt):
        return utc_dt.astimezone(self.shtime.tzinfo())

    def _resolve_to_utc(self, dt, moff=0):
        """Resolve an optional dt parameter (None/naive/aware) to a UTC datetime,
        applying the minute offset the same way for all callers."""
        if dt is None:
            return (
                self.shtime.utcnow()
                - dateutil.relativedelta.relativedelta(minutes=moff)
                + dateutil.relativedelta.relativedelta(seconds=2)
            )
        if dt.tzinfo is None:
            return self.unaware_datetime_to_utc(dt) - dateutil.relativedelta.relativedelta(minutes=moff)
        return self.aware_datetime_to_utc(dt) - dateutil.relativedelta.relativedelta(minutes=moff)

    def _avoid_neverup(self, dt, date_utc, doff):
        """
        When specifying an offset for e.g. a sunset or a sunrise it might well be that the
        offset is too high to be ever reached for a specific location and time
        Therefore this function will limit this offset and return it to the calling function

        :param dt: starting point for calculation
        :type dt: datetime
        :param date_utc: a datetime with utc time
        :type date_utc: datetime
        :param doff: offset in degrees
        :type doff: float
        :return: corrected offset in degrees
        :rtype: float
        """
        originaldoff = doff

        # Get times for noon and midnight
        midnight = self.midnight(0, 0, dt=dt)
        noon = self.noon(0, 0, dt=dt)

        # If the altitudes are calculated from previous or next day, set the correct day for the observer query
        noon = noon if noon >= date_utc else self.noon(0, 0, dt=date_utc + dateutil.relativedelta.relativedelta(days=1))
        midnight = (
            midnight
            if midnight >= date_utc
            else self.midnight(0, 0, dt=date_utc - dateutil.relativedelta.relativedelta(days=1))
        )
        # Get lowest and highest altitudes of the relevant day/night
        max_altitude = (
            self.pos(offset=None, degree=True, dt=midnight)[1]
            if doff <= 0
            else self.pos(offset=None, degree=True, dt=noon)[1]
        )

        # Limit degree offset to the highest or lowest possible for the given date
        doff = (
            max(doff, max_altitude + self.neverup_delta)
            if doff < 0
            else min(doff, max_altitude - self.neverup_delta)
            if doff > 0
            else doff
        )
        if not originaldoff == doff:
            logger.notice(f'offset {originaldoff} truncated to {doff}')
        return doff

    def noon(self, doff=0, moff=0, dt=None):
        """
        calculate the time of next transit starting with dt. If dt is None the the time of this function call will be used

        :param doff: degrees offset, defaults to 0
        :type doff: float, optional
        :param moff: minutes offset, defaults to 0
        :type moff: float, optional
        :param dt: datetime object to start calculation with, defaults to None
        :type dt: datetime, optional
        :return: datetime of next transit
        :rtype: datetime
        """
        date_utc = self._resolve_to_utc(dt, moff)
        logger.debug(f'noon for {self.orb} with doff={doff}, moff={moff}, dt={dt}, resolved date_utc={date_utc}')

        # attention: _avoid_neverup itself calls noon(), this might well get circular in some circumstances
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        next_transit = self._backend.next_transit(self.lon, self.lat, self.elev, self.orb, date_utc, doff)
        next_transit = next_transit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_transit = next_transit.replace(tzinfo=tzutc())
        logger.debug(f'noon for {self.orb} with doff={doff}, moff={moff}, dt={dt} will be {next_transit}')
        return next_transit

    def midnight(self, doff=0, moff=0, dt=None):
        """
        Calculate the time of next antitransit starting with dt. If dt is None the the time of this function call will be used

        :param doff: degrees offset, defaults to 0
        :type doff: float, optional
        :param moff: minutes offset, defaults to 0
        :type moff: float, optional
        :param dt: datetime object to start calculation with, defaults to None
        :type dt: datetime, optional
        :return: datetime of next antitransit
        :rtype: datetime
        """
        date_utc = self._resolve_to_utc(dt, moff)
        logger.debug(f'midnight for {self.orb} with doff={doff}, moff={moff}, dt={dt}, resolved date_utc={date_utc}')

        # attention: _avoid_neverup itself calls noon(), this might well get circular in some circumstances
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        next_antitransit = self._backend.next_antitransit(self.lon, self.lat, self.elev, self.orb, date_utc, doff)
        next_antitransit = next_antitransit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_antitransit = next_antitransit.replace(tzinfo=tzutc())
        logger.debug(f'midnight for {self.orb} with doff={doff}, moff={moff}, dt={dt} will be {next_antitransit}')
        return next_antitransit

    def rise(self, doff=0, moff=0, center=True, dt=None):
        """
        Computes the rise of either sun or moon
        :param doff:    degrees offset for the observers horizon
        :param moff:    minutes offset from time of rise (either before or after)
        :param center:  if True then the centerpoint of either sun or moon will be considered to make the transit otherwise the upper limb will be considered
        :param dt:      start time for the search for a rise, if not given the current time will be used
        :return: datetime of next rising in utc timezone, or None if the body does not rise during this circuit
        """
        # _resolve_to_utc adds 2 seconds when dt is None, working around rise being 0.001s in the past
        date_utc = self._resolve_to_utc(dt, 0)
        logger.debug(f'rise for {self.orb} with doff={doff}, moff={moff}, dt={dt}, resolved date_utc={date_utc}')

        # attention: _avoid_neverup itself calls noon(), this might well get circular in some circumstances
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        next_rising = self._backend.next_rising(self.lon, self.lat, self.elev, self.orb, date_utc, doff, center)
        if next_rising is None:
            return None
        if not doff == 0:
            next_real_rising = self._backend.next_rising(self.lon, self.lat, self.elev, self.orb, date_utc, 0, center)
            if next_real_rising is None:
                return None
        else:
            next_real_rising = next_rising

        next_rising = next_rising + dateutil.relativedelta.relativedelta(minutes=moff)
        next_rising = next_rising.replace(tzinfo=tzutc())
        if doff < 0 and next_rising > next_real_rising:
            logger.debug(f'adjusted next_rising {next_rising} to previous day as it is later than {next_real_rising}')
            next_rising -= datetime.timedelta(days=1)
        logger.debug(
            f'next_rising for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_rising}'
        )
        return next_rising

    def set(self, doff=0, moff=0, center=True, dt=None):
        """
        Computes the setting of either sun or moon
        :param doff:    degrees offset for the observers horizon
        :param moff:    minutes offset from time of setting (either before or after)
        :param center:  if True then the centerpoint of either sun or moon will be considered to make the transit otherwise the upper limb will be considered
        :param dt:      start time for the search for a setting, if not given the current time will be used
        :return: datetime of next setting in utc timezone, or None if the body does not set during this circuit
        """
        # _resolve_to_utc adds 2 seconds when dt is None, working around set being 0.001s in the past
        date_utc = self._resolve_to_utc(dt, 0)
        logger.debug(f'set for {self.orb} with doff={doff}, moff={moff}, dt={dt}, resolved date_utc={date_utc}')

        # avoid NeverUp error
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        next_setting = self._backend.next_setting(self.lon, self.lat, self.elev, self.orb, date_utc, doff, center)
        if next_setting is None:
            return None
        if not doff == 0:
            next_real_setting = self._backend.next_setting(self.lon, self.lat, self.elev, self.orb, date_utc, 0, center)
            if next_real_setting is None:
                return None
        else:
            next_real_setting = next_setting

        next_setting = next_setting + dateutil.relativedelta.relativedelta(minutes=moff)
        next_setting = next_setting.replace(tzinfo=tzutc())
        if doff < 0 and next_setting < next_real_setting:
            logger.debug(
                f'adjusted next_setting {next_setting} to next day as it is earlier than actual sunset at {next_real_setting}'
            )
            next_setting += datetime.timedelta(days=1)
        logger.debug(
            f'next_setting for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_setting}'
        )
        return next_setting

    def pos(self, offset=None, degree=False, dt=None):
        """
        Calculates the position of either sun or moon
        :param offset:  given in minutes, shifts the time of calculation by some minutes back or forth
        :param degree:  if True: return the position of either sun or moon from the observer as degrees, otherwise as radians
        :param dt:      time for which the position needs to be calculated
        :return:        a tuple with azimuth and elevation
        """
        if dt is None:
            date = self.shtime.utcnow()
            logger.debug(f'pos for {self.orb} with offset={offset}, degree={degree}, dt is None, using now={date}')
        elif dt.tzinfo is None:
            logger.debug(f'pos for {self.orb} with offset={offset}, degree={degree}, dt={dt}, assuming local time')
            date = self.unaware_datetime_to_utc(dt)
        else:
            logger.debug(
                f'pos for {self.orb} with offset={offset}, degree={degree}, dt={dt}, dt timezone is {dt.tzinfo}'
            )
            date = self.aware_datetime_to_utc(dt)

        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        az, alt = self._backend.position(self.lon, self.lat, self.elev, self.orb, date)

        if degree:
            return (math.degrees(az), math.degrees(alt))
        else:
            return (az, alt)

    def _light(self, offset=None):
        """
        Applies only for moon, returns fraction of lunar surface illuminated when viewed from earth
        for the current time plus an offset
        :param offset: an offset given in minutes
        """
        date = self.shtime.utcnow()
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)
        return self._backend.moon_light_percent(self.lon, self.lat, self.elev, date)

    def _phase(self, offset=None):
        """
        Applies only for moon, returns the moon phase related to a cycle of approx. 29.5 days
        for the current time plus an offset
        :param offset: an offset given in minutes
        """
        date = self.shtime.utcnow()
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)
        return self._backend.moon_phase_octant(self.lon, self.lat, self.elev, date)
