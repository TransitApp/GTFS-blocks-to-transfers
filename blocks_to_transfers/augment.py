from datetime import timedelta
from collections import namedtuple
from .editor.schema import *


DAY_SEC = 86400
TripSpan = namedtuple('TripSpan', ('data', 'first_departure', 'last_arrival', 'shifted_services'))

class GTFSAugmented(Entity):
    def __init__(self, gtfs, days_by_service, trips_by_block):
        super().__init__(**gtfs)
        self.days_by_service = days_by_service
        self.trips_by_block = trips_by_block


def augment(gtfs):
    return GTFSAugmented(gtfs,
                         get_days_by_service(gtfs),
                         group_trips_by_block(get_trip_spans(gtfs)))


def get_days_by_service(gtfs):
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





def get_trip_spans(gtfs):
    trip_spans = []

    for trip in gtfs.trips.values():
        first_departure = gtfs.stop_times[trip.trip_id][0].departure_time
        last_arrival = gtfs.stop_times[trip.trip_id][-1].arrival_time
        day_shift = 0 if first_departure < DAY_SEC else DAY_SEC
        trip_spans.append(TripSpan(
            trip,
            first_departure - day_shift,
            last_arrival - day_shift,
            shifted_services=day_shift != 0
        ))

    trip_spans.sort(key=lambda trip: trip.first_departure)
    return trip_spans


def group_trips_by_block(trip_spans):
    trips_by_block = {}

    for trip in trip_spans:
        if not trip.data.block_id:
            continue

        trips_by_block.setdefault(trip.data.block_id, []).append(trip)

    return trips_by_block

