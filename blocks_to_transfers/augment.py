"""
Computes data structures that make converting blocks to transfers more efficient.
"""

from datetime import timedelta

from . import config
from .editor.schema import *


class GTFSAugmented:
    def __init__(self, gtfs, days_by_service, trips_by_block):
        self.gtfs = gtfs
        self.days_by_service = days_by_service
        self.trips_by_block = trips_by_block
        self.shape_similarity_results = {}

# ,


def augment(gtfs):
    return GTFSAugmented(
        gtfs,
        get_days_by_service(gtfs),
        group_trips_by_block(augment_trips(gtfs)),
    )


def get_days_by_service(gtfs):
    print('Calculating days by service')
    all_service_ids = gtfs.calendar.keys() | gtfs.calendar_dates.keys()
    days_by_service = {}
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for service_id in all_service_ids:
        service_days = days_by_service[service_id] = set()
        calendar = gtfs.calendar.get(service_id)
        if calendar:
            num_days = (calendar.end_date - calendar.start_date).days + 1
            current_day = calendar.start_date
            for _ in range(num_days):
                weekday_name = weekdays[current_day.weekday()]

                if calendar[weekday_name]:
                    service_days.add(current_day)

                current_day += timedelta(days=1)

        for date in gtfs.calendar_dates.get(service_id, []):
            if date.exception_type == ExceptionType.ADD:
                if date.date in service_days:
                    print(f'Warning: calendar_dates.txt adds {date.date} to {service_id} even though it already runs on this date')
                service_days.add(date.date)
            else:
                if date.date not in service_days:
                    print(f'Warning: calendar_dates.txt removes {date.date} from {service_id} even though it already is not running on this date')
                service_days.discard(date.date)

    return days_by_service


def augment_trips(gtfs):
    print('Merging shapes of identical trip stop sequences')
    unique_shapes = {}
    trips = []
    for trip in list(gtfs.trips.values()):
        if len(gtfs.stop_times.get(trip.trip_id, [])) < 2:
            print(f'Warning: Trip {trip.trip_id} deleted as it has fewer than two stops.')
            continue

        if config.InSeatTransfers.ignore_return_via_similar_trip:
            trip.shape_ref = unique_shapes.setdefault(trip.stop_shape, trip.stop_shape)
        trips.append(trip)

    trips.sort(key=lambda trip: trip.first_departure)
    return trips


def group_trips_by_block(trips):
    trips_by_block = {}

    for trip in trips:
        if not trip.block_id:
            continue

        trips_by_block.setdefault(trip.block_id, []).append(trip)

    return trips_by_block