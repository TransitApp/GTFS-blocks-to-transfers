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


GTFS_SUBSET_SCHEMA = Schema(
    File(
        id='service_id',
        name='calendar',
        required=False,
        fields=dict(
            service_id=Field(required=True),
            monday=Field(required=True, validator=as_bool),
            tuesday=Field(required=True, validator=as_bool),
            wednesday=Field(required=True, validator=as_bool),
            thursday=Field(required=True, validator=as_bool),
            friday=Field(required=True, validator=as_bool),
            saturday=Field(required=True, validator=as_bool),
            sunday=Field(required=True, validator=as_bool),
            start_date=Field(required=True, validator=GTFSDate),
            end_date=Field(required=True, validator=GTFSDate),
        )
    ),
    File(
        id='service_id',
        name='calendar_dates',
        group_sort_key='date',
        required=False,
        fields=dict(
            service_id=Field(required=True),
            date=Field(required=True, validator=GTFSDate),
            exception_type=Field(required=True, validator=as_enum(ExceptionType)),
        )
    ),
    File(
        id='trip_id',
        name='trips',
        fields=dict(
            service_id=Field(required=True),
            trip_id=Field(required=True),
            block_id=Field(required=False),
            shape_id=Field(required=False),
        ),
    ),
    File(
        id='stop_id',
        name='stops',
        fields=dict(
            stop_id=Field(required=True),
            stop_lat=Field(required=True, validator=as_lat),
            stop_lon=Field(required=True, validator=as_lon)
        )
    ),
    File(
        id='shape_id',
        name='shapes',
        required=False,
        group_sort_key='shape_pt_sequence',
        fields=dict(
            shape_id=Field(required=True),
            shape_pt_lat=Field(required=True, validator=as_lat),
            shape_pt_lon=Field(required=True, validator=as_lon),
            shape_pt_sequence=Field(required=True,validator=int)
        )
    ),
    File(
        id='trip_id',
        name='stop_times',
        group_sort_key='stop_sequence',
        fields=dict(
            stop_id=Field(required=True),
            trip_id=Field(required=True),
            arrival_time=Field(required=False, validator=GTFSTime),
            departure_time=Field(required=False, validator=GTFSTime),
            stop_sequence=Field(required=True, validator=int),
        )
    ),
    File(
        id='from_trip_id',
        name='transfers',
        required=False,
        group_sort_key='to_trip_id',
        fields=dict(
            from_trip_id=Field(required=True),
            to_trip_id=Field(required=True),
            transfer_type=Field(required=False, validator=as_enum(TransferType, default=TransferType.RECOMMENDED))
        )
    )
)
