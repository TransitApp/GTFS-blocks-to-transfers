from collections import namedtuple
from datetime import timedelta

from . import config
from .editor.schema import *
from .shape_similarity import LatLon

DAY_SEC = 86400


class GTFSAugmented:
    def __init__(self, gtfs, days_by_service, trips_by_block):
        self.gtfs = gtfs
        self.days_by_service = days_by_service
        self.trips_by_block = trips_by_block
        self.shape_similarity_results = {}
        self.num_split_services = 0
        self.num_duplicated_trips = 0


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
    print('Calculating trip timespans and stop shapes')
    unique_shapes = {}
    trips = []
    for trip in list(gtfs.trips.values()):
        if len(gtfs.stop_times.get(trip.trip_id, [])) < 2:
            print(f'Warning: Trip {trip.trip_id} deleted as it has fewer than two stops.')
            continue

        set_span(gtfs, trip)
        if config.InSeatTransfers.ignore_return_via_similar_trip:
            set_shape(unique_shapes, gtfs, trip)
        trips.append(trip)

    trips.sort(key=lambda trip: trip.first_departure)
    return trips


def set_span(gtfs, trip):
    first_st = gtfs.stop_times[trip.trip_id][0]
    last_st = gtfs.stop_times[trip.trip_id][-1]
    day_shift = 0 if first_st.departure_time < DAY_SEC else DAY_SEC

    trip.first_departure = first_st.departure_time - day_shift
    trip.last_arrival = last_st.arrival_time - day_shift
    trip.one_day_forward_of_service = day_shift != 0

    first_stop = gtfs.stops[first_st.stop_id]
    trip.first_stop = LatLon(first_stop.stop_lat, first_stop.stop_lon)
    last_stop = gtfs.stops[last_st.stop_id]
    trip.last_stop = LatLon(last_stop.stop_lat, last_stop.stop_lon)


def set_shape(unique_shapes, gtfs, trip):
    """
    A trip's shape can be used to predict whether or not the continuation is an in-seat transfer. For performance reasons,
    we always use the trip's sequence of stops, even if a GTFS shape is provided for the trip,.
    """

    stop_shape = []
    for stop_time in gtfs.stop_times[trip.trip_id]:
        stop = gtfs.stops[stop_time.stop_id]
        stop_shape.append(LatLon(stop.stop_lat, stop.stop_lon))

    stop_shape = tuple(stop_shape)
    trip.shape = unique_shapes.setdefault(stop_shape, stop_shape)


def group_trips_by_block(trip_spans):
    trips_by_block = {}

    for trip in trip_spans:
        if not trip.block_id:
            continue

        trips_by_block.setdefault(trip.block_id, []).append(trip)

    return trips_by_block

