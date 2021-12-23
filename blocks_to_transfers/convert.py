from collections import namedtuple
from datetime import timedelta
from enum import Enum
from . import config, shape_similarity
from .augment import DAY_SEC
from .editor import duplicate
from .editor.schema import TransferType, Transfer

"""
TODO: 
1. test cases
3. readme
5. midnight shift
7. lookup existing services or make a new fake
8. dupe trip
"""


def convert_blocks(data):
    print('Predicting continuations')

    for trips in data.trips_by_block.values():
        try:
            convert_block(data, trips)
        except InvalidBlockError as exc:
            print(str(exc))


def convert_block(data, trips):
    for i_trip, trip in enumerate(trips):
        if not config.TripToTripTransfers.overwrite_existing and trip in data.gtfs.transfers:
            continue

        trip_transfers = []
        days_to_match = get_days(data.days_by_service, trip)

        try:
            for cont_trip in trips[i_trip + 1:]:
                transfer_opt = consider_transfer(data, days_to_match, trip, cont_trip)
                if transfer_opt:
                    trip_transfers.append(transfer_opt)

            # The transfer may be after midnight

            for cont_trip in trips[:i_trip]:
                transfer_opt = consider_transfer(data, days_to_match, trip, cont_trip,
                                                        after_midnight=True)
                if transfer_opt:
                    trip_transfers.append(transfer_opt)


        except StopIteration:
            # Will be raised once we know that there's no further trips to consider for transfers
            pass

        # If days_to_match is not empty, it results in an additional case where trip has no continuation on certain days
        # of service, but we do not need to explicitly store this, as the trip-to-trip transfers we do write will be
        # ignored unless both trips are operating

        insert_transfers(data, trip, trip_transfers)


def insert_transfers(data, from_trip, to_trips):
    if not to_trips:
        return

    if len(to_trips) == 1:
        insert_transfer(data, from_trip, to_trips[0])
        return

    # There are 2+ continuations, depending on the day of service.
    # For each transfer:
    # (1) Duplicate the trip with a new ID. Duplicate all of its stop times
    # (2) Is there an existing service with the same days as this continuation? If so set the service ID
    # (3) Create a set of calendar_dates describing this new service
    # (4) Insert the transfer to the duplicate trip
    for to_trip in to_trips:
        cloned_trip_id =  f'{from_trip.trip_id}-blocks2transfers{data.num_duplicated_trips}'
        cloned_trip = duplicate(data.gtfs.trips, from_trip.trip_id, cloned_trip_id)
        duplicate(data.gtfs.stop_times, from_trip.trip_id, cloned_trip_id)
        data.num_duplicated_trips += 1
        # DANGER DANGER WHAT IF A SPLIT TRIP REFERS TO ANOTHER SPLIT TRIP
        insert_transfer(data, cloned_trip, to_trip)

    del data.gtfs.trips[from_trip.trip_id]
    del data.gtfs.stop_times[from_trip.trip_id]


def insert_transfer(data, from_trip, to_trip):
    current_transfers = data.gtfs.transfers.setdefault(from_trip.trip_id, [])
    current_transfers.append(Transfer(
        from_trip_id=from_trip.trip_id,
        to_trip_id=to_trip.trip.trip_id,
        transfer_type=to_trip.transfer_type
    ))


def pdates(dates):
    sdates = sorted(date.strftime('%m%d') for date in dates)
    tdates =  ', '.join(sdates[:14])
    if len(dates) > 14:
        tdates += ' ...'
    return tdates


def get_days(days_by_service, trip):
    service_days = days_by_service[trip.service_id]
    if trip.one_day_forward_of_service:
        return {day + timedelta(days=1) for day in service_days}
    else:
        return set(service_days) # Need a copy to modify


class InvalidBlockError(ValueError):
    def __init__(self, trip, cont_trip):
        super().__init__(self, 'Invalid block')
        self.trip = trip
        self.cont_trip = cont_trip
        
    def __str__(self):
        wait_time = self.cont_trip.first_departure - self.trip.last_arrival
        block_id = self.trip.block_id

        return f'''
        Warning: Block {block_id} is invalid:
                {self.trip.first_departure} - {self.trip.last_arrival} [{self.trip.trip_id}]
                {self.cont_trip.first_departure} - {self.cont_trip.last_arrival} [{self.cont_trip.trip_id}]
                In two places at once for {abs(wait_time)} s.
        '''


TransferResult = namedtuple('TransferResult', ('transfer_type', 'trip', 'days_when_best'))


def consider_transfer(data, days_to_match, trip, cont_trip, after_midnight=False):
    wait_time = cont_trip.first_departure - trip.last_arrival

    if after_midnight:
        wait_time += DAY_SEC

    # First check if cont_trip is a valid trip-to-trip transfer
    days_when_best = match_transfer(data, days_to_match, trip, wait_time, cont_trip)
    if not days_when_best:
        return None

    transfer_type = classify_transfer(data, trip, wait_time, cont_trip)
    return TransferResult(transfer_type, cont_trip, days_when_best)


def match_transfer(data, days_to_match, trip, wait_time, cont_trip):
    # transfer found for every day trip operates on
    if not days_to_match:
        raise StopIteration

    # Wait time too long even for operational purposes
    if wait_time > config.TripToTripTransfers.max_wait_time:
        raise StopIteration

    days_when_best = get_days(data.days_by_service, cont_trip)
    days_when_best.intersection_update(days_to_match)

    # A: trip and cont_trip never run on the same day; or
    # B: There's no day cont_trip runs on that isn't served by an earlier trip
    if not days_when_best:
        return set()

    # We know that trip and cont_trip operate together on at least one day, and yet there's no way a single
    # vehicle can do this.
    if wait_time < 0:
        if config.TripToTripTransfers.force_allow_invalid_blocks:
            return set()
        else:
            raise InvalidBlockError(trip, cont_trip)

    days_to_match.difference_update(days_when_best)
    return days_when_best


def classify_transfer(data, trip, wait_time, cont_trip):
    # transfer would require riders to wait for an excessively long time
    if wait_time > config.InSeatTransfers.max_wait_time:
        return TransferType.VEHICLE_CONTINUATION

    # cont_trip resumes too far away from where trip ended (probably involves deadheading)
    if trip.last_stop.dist_to(cont_trip.first_stop) > config.InSeatTransfers.same_location_distance:
        return TransferType.VEHICLE_CONTINUATION

    # trip and cont_trip form a loop, therefore any similarity in shape is not an issue for riders
    if (trip.first_stop.dist_to(cont_trip.first_stop) < config.InSeatTransfers.same_location_distance
        and trip.last_stop.dist_to(cont_trip.last_stop) < config.InSeatTransfers.same_location_distance):
        return TransferType.IN_SEAT

    if config.InSeatTransfers.ignore_return_via_same_route:
        if trip.route_id == cont_trip.route_id and trip.direction_id != cont_trip.direction_id:
            return TransferType.VEHICLE_CONTINUATION

    if config.InSeatTransfers.ignore_return_via_similar_trip:
        if shape_similarity.trip_shapes_similar(data.shape_similarity_results, trip.shape, cont_trip.shape):
            return TransferType.VEHICLE_CONTINUATION

    # We presume that the rider will be able to stay onboard the vehicle
    return TransferType.IN_SEAT