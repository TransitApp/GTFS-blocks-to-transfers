import math
from enum import IntEnum
from functools import cached_property
from typing import Optional
from .schema_classes import *
from .types import *
from ..shape_similarity import LatLon

DAY_SEC = 86400


class ExceptionType(IntEnum):
    ADD = 1
    REMOVE = 2


class TransferType(IntEnum):
    RECOMMENDED = 0
    TIMED = 1
    MINIMUM_TIME = 2
    NOT_POSSIBLE = 3
    IN_SEAT = 4
    VEHICLE_CONTINUATION = 5


class Calendar(Entity):
    _schema = File(id='service_id', name='calendar', required=False)

    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: GTFSDate
    end_date: GTFSDate


class CalendarDate(Entity):
    _schema = File(id='service_id',
                   name='calendar_dates',
                   group_id='date',
                   required=False)

    service_id: str
    date: GTFSDate
    exception_type: ExceptionType


class Trip(Entity):
    _schema = File(id='trip_id', name='trips', required=True)

    trip_id: str
    service_id: str
    block_id: str = ''
    route_id: str

    @property
    def first_stop_time(self):
        return self._gtfs.stop_times[self.trip_id][0]

    @property
    def last_stop_time(self):
        return self._gtfs.stop_times[self.trip_id][-1]

    @property
    def stop_shape(self):
        return tuple(self._gtfs.stops[st.stop_id].location
                     for st in self._gtfs.stop_times[self.trip_id])

    @cached_property
    def shift_days(self):
        return 1 if self.first_stop_time.departure_time >= DAY_SEC else 0

    @cached_property
    def first_departure(self):
        if self.trip_id not in self._gtfs.stop_times:
            return -math.inf

        return self.first_stop_time.departure_time - DAY_SEC * self.shift_days

    @cached_property
    def last_arrival(self):
        return self.last_stop_time.arrival_time - DAY_SEC * self.shift_days

    @cached_property
    def first_point(self):
        return self._gtfs.stops[self.first_stop_time.stop_id].location

    @cached_property
    def last_point(self):
        return self._gtfs.stops[self.last_stop_time.stop_id].location


# Currently not parsed for performance reasons
class Shape(Entity):
    _schema = File(id='shape_id',
                   name='shapes',
                   required=False,
                   group_id='shape_pt_sequence')

    shape_id: str
    shape_pt_sequence: int
    shape_pt_lat: float
    shape_pt_lon: float


class Stop(Entity):
    _schema = File(id='stop_id', name='stops', required=True)

    stop_id: str
    stop_lat: Optional[float] = None
    stop_lon: Optional[float] = None

    @cached_property
    def location(self):
        if self.stop_lat is None or self.stop_lon is None:
            raise ValueError(f'Stop {self.stop_id} missing location')

        return LatLon(self.stop_lat, self.stop_lon)


class Transfer(Entity):
    _schema = File(id='from_trip_id',
                   name='transfers',
                   required=False,
                   group_id='to_trip_id')

    from_trip_id: str = ''
    to_trip_id: str = ''
    transfer_type: TransferType = TransferType.RECOMMENDED

    @property
    def is_continuation(self):
        return self.transfer_type in {
            TransferType.IN_SEAT, TransferType.VEHICLE_CONTINUATION
        }

    @property
    def is_generated(self):
        return hasattr(self, '_rank')


class StopTime(Entity):
    _schema = File(id='trip_id',
                   name='stop_times',
                   required=True,
                   group_id='stop_sequence')

    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_time: GTFSTime = GTFSTime('')
    departure_time: GTFSTime = GTFSTime('')

    @property
    def stop(self):
        return self._gtfs.stops[self.stop_id]


GTFS_SUBSET_SCHEMA = Schema(Calendar, CalendarDate, Trip, Stop, Transfer,
                            StopTime)
