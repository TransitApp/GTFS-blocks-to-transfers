"""
For every trip within a block, identifies valid continuation trips on each day of service.
"""
from collections import namedtuple
from gtfs_loader.schema import Transfer, DAY_SEC
from . import config, service_days
from .logs import Warn
import math

BlockConvertState = namedtuple('BlockConvertState',
                               ('gtfs', 'services', 'shape_similarity_results'))


class TripConvertState:

    def __init__(self, data, trip) -> None:
        self.trip = trip
        self.shift_days = 0
        self.days_to_match = data.services.days_by_trip(trip)
        self.num_matches = 0


def convert(gtfs, services):
    print('Predicting continuation trip for trips within blocks')
    trips_by_block = group_trips(gtfs)
    converted_transfers = []
    data = BlockConvertState(gtfs, services, {})

    for trips in trips_by_block.values():
        try:
            converted_transfers.extend(convert_block(data, trips))
        except Warn as exc:
            exc.print()

    return converted_transfers


def group_trips(gtfs):
    unique_shapes = {}
    trips_by_block = {}

    for trip in sorted(gtfs.trips.values(),
                       key=lambda trip: trip.first_departure):
        if not trip.block_id:
            continue

        if len(gtfs.stop_times.get(trip.trip_id, [])) < 2:
            Warn(f'Trip {trip.trip_id} deleted as it has fewer than two stops.'
                ).print()
            continue

        if config.InSeatTransfers.ignore_return_via_similar_trip:
            trip.shape_ref = unique_shapes.setdefault(trip.stop_shape,
                                                      trip.stop_shape)

        trips_by_block.setdefault(trip.block_id, []).append(trip)

    return trips_by_block


def convert_block(data, trips):
    converted_transfers = []

    for i_trip, trip in enumerate(trips):
        trip_state = TripConvertState(data, trip)

        try:
            for cont_trip in trips[i_trip + 1:]:
                transfer_opt = consider_transfer(data, trip_state, cont_trip)
                if transfer_opt:
                    converted_transfers.append(transfer_opt)

            # Search continues onto the next day; shift days of service from continuation trips back one day to match
            # the notation used to describe trip
            trip_state.shift_days += 1

            for cont_trip in trips[:i_trip]:
                transfer_opt = consider_transfer(data, trip_state, cont_trip)
                if transfer_opt:
                    converted_transfers.append(transfer_opt)
        except StopIteration:
            # Will be raised once we know that there's no further trips to consider for transfers
            pass

    return converted_transfers


def consider_transfer(data, trip_state, cont_trip):
    wait_time = cont_trip.first_departure - trip_state.trip.last_arrival

    if trip_state.shift_days > 0:
        wait_time += DAY_SEC

    # transfer found for every day trip operates on
    if not trip_state.days_to_match:
        raise StopIteration

    # Wait time too long even for operational purposes
    if wait_time > config.TripToTripTransfers.max_wait_time:
        raise StopIteration

    cont_days_in_from_frame = data.services.days_by_trip(
        cont_trip, -trip_state.shift_days)  # From trip's frame of reference

    # Can only match on days originating trip is running
    days_when_best = cont_days_in_from_frame.intersection(
        trip_state.days_to_match)

    # A: trip and cont_trip never run on the same day; or
    # B: There's no day cont_trip runs on that isn't served by an earlier trip
    if not days_when_best:
        return None

    # We know that trip and cont_trip operate together on at least one day, and yet there's no way a single
    # vehicle can do this.
    if not valid_wait_time(trip_state.trip,
                           cont_trip,
                           wait_time,
                           debug_context=data.services.pdates(days_when_best)):
        return None

    if not reasonable_deadheading_speed(
            trip_state.trip,
            cont_trip,
            wait_time,
            debug_context=data.services.pdates(days_when_best)):
        return None

    trip_state.days_to_match = trip_state.days_to_match.difference(
        days_when_best)
    trip_state.num_matches += 1

    return Transfer(from_trip_id=trip_state.trip.trip_id,
                    to_trip_id=cont_trip.trip_id,
                    _rank=trip_state.num_matches)


KM_H_FACTOR = 3.6  # Conversion factor between m/s and km/h


def reasonable_deadheading_speed(trip, cont_trip, wait_time, debug_context):
    dist = trip.last_point.distance_to(cont_trip.first_point)
    if dist < config.TripToTripTransfers.max_nearby_deadheading_distance:
        return True

    speed = KM_H_FACTOR * dist / wait_time if wait_time else math.inf

    if speed > config.TripToTripTransfers.max_deadheading_speed:
        Warn(f'''
        Block {trip.block_id} is invalid - attempting auto-fix:
            | {trip.first_departure} {trip.first_stop_time.stop.stop_name} [trip {trip.trip_id}]
            v {trip.last_arrival} {trip.last_stop_time.stop.stop_name} [trip {trip.trip_id}]
            \t(!) Would require travelling {dist/1000:.2f} km at {speed:.0f} km/h (!)
            | {cont_trip.first_departure} {cont_trip.first_stop_time.stop.stop_name} [trip {cont_trip.trip_id}] 
            v {cont_trip.last_arrival} {cont_trip.last_stop_time.stop.stop_name} [trip {cont_trip.trip_id}]
            
            Occurs on days {debug_context}.
        ''').print()
        return False

    return True


def valid_wait_time(trip, cont_trip, wait_time, debug_context):

    def trip_desc(char, trip, time):
        return f'{char} {time} [trip {trip.trip_id}]'

    if wait_time >= 0:
        return True

    action = 'attempting auto-fix' if config.TripToTripTransfers.force_allow_invalid_blocks else 'deleted'
    block_error = Warn(f'''
        Block {trip.block_id} is invalid - {action}:
            {trip_desc('|', trip, trip.first_departure):<60}\t\t{trip_desc('|', cont_trip, cont_trip.first_departure):<60} 
            {trip_desc('v', trip, trip.last_arrival):<60}\t\t{trip_desc('v', cont_trip, cont_trip.last_arrival):<60}
            \t\t(!) In two places at once for {abs(wait_time)} s (!)

            Occurs on days {debug_context}.
    ''')

    if config.TripToTripTransfers.force_allow_invalid_blocks:
        block_error.print()
        return False
    else:
        raise block_error
