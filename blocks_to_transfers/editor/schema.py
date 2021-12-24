from enum import IntEnum
from .schema_classes import *
from .types import *


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
    SCHEMA = File(id='service_id', name='calendar', required=False)

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
    SCHEMA = File(id='service_id', name='calendar_dates', group_sort_key='date', required=False)

    service_id: str
    date: GTFSDate
    exception_type: ExceptionType


class Trip(Entity):
    SCHEMA = File(id='trip_id', name='trips', required=True)

    trip_id: str
    service_id: str
    shape_id: str = ''
    block_id: str = ''
    route_id: str


# Currently not parsed for performance reasons
class Shape(Entity):
    SCHEMA = File(id='shape_id', name='shapes', required=False, group_sort_key='shape_pt_sequence')

    shape_id: str
    shape_pt_sequence: int
    shape_pt_lat: float
    shape_pt_lon: float


class Stop(Entity):
    SCHEMA = File(id='stop_id', name='stops', required=True)

    stop_id: str
    stop_lat: float
    stop_lon: float

class Transfer(Entity):
    SCHEMA = File(id='from_trip_id', name='transfers', required=False, group_sort_key='to_trip_id')

    from_trip_id: str = ''
    to_trip_id: str = ''
    transfer_type: TransferType = TransferType.RECOMMENDED


class StopTime(Entity):
    SCHEMA = File(id='trip_id', name='stop_times', required=True, group_sort_key='stop_sequence')

    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_time: GTFSTime = GTFSTime('')
    departure_time: GTFSTime = GTFSTime('')


GTFS_SUBSET_SCHEMA = Schema(Calendar, CalendarDate, Trip, Stop, Transfer, StopTime)
