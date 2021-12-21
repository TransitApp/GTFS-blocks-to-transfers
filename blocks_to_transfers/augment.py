import math
from datetime import timedelta
from .editor.schema import *
from .shape_similarity import LatLon

DAY_SEC = 86400


class GTFSAugmented(Entity):
    def __init__(self, gtfs, days_by_service, trips_by_block):
        super().__init__(**gtfs)
        self.days_by_service = days_by_service
        self.trips_by_block = trips_by_block


class TripAugmented(Entity):
    def __init__(self, trip, first_departure, last_arrival, shifted_services):
        super().__init__(**trip)
        self.first_departure = first_departure
        self.last_arrival = last_arrival
        self.shifted_services = shifted_services
        self.stop_shape = []
        self.stop_shape_key = None


def augment(gtfs):
    augment_trips


    return GTFSAugmented(gtfs,
                         get_days_by_service(gtfs),
                         group_trips_by_block(get_trip_stop_shapes(gtfget_trip_spans(gtfs)))


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
        if trip.trip_id not in gtfs.stop_times:
            print(trip.trip_id, 'is bogus')
            continue

        first_departure = gtfs.stop_times[trip.trip_id][0].departure_time
        last_arrival = gtfs.stop_times[trip.trip_id][-1].arrival_time
        day_shift = 0 if first_departure < DAY_SEC else DAY_SEC
        trip_spans.append(TripAugmented(
            trip,
            first_departure - day_shift,
            last_arrival - day_shift,
            shifted_services=day_shift != 0
        ))

    trip_spans.sort(key=lambda trip: trip.first_departure)
    return trip_spans

def get_trip_stop_shapes(gtfs):



def get_trip_shape(gtfs, trip):
    return [LatLon(gtfs.stops[st.stop_id].stop_lat, gtfs.stops[st.stop_id].stop_lon)
            for st in gtfs.stop_times[trip.trip_id]]

    if trip.shape_id:
        pts = [LatLon(pt.shape_pt_lat, pt.shape_pt_lon) for pt in gtfs.shapes[trip.shape_id]]
        """
        simple_pts = [pts[0]]
        eps = math.pi / 360
        for i in range(len(pts) - 1):
            if abs(pts[i].bearing_to(pts[i+1])) > eps:
                simple_pts.append(pts[i+1])

        if len(simple_pts) == 1:
            simple_pts.append(pts[-1])
        if len(simple_pts) < len(pts):
            print('simplified', len(simple_pts), len(pts))
        """
        return pts





def group_trips_by_block(trip_spans):
    trips_by_block = {}

    for trip in trip_spans:
        if not trip.block_id:
            continue

        trips_by_block.setdefault(trip.block_id, []).append(trip)

    return trips_by_block

