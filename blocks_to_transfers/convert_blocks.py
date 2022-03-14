"""
For every trip within a block, identifies valid continuation trips on each day of service.
"""
from collections import namedtuple
from .editor.schema import Transfer, DAY_SEC
from . import config, service_days

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
        if not may_convert_trips(gtfs, trips):
            continue

        try:
            converted_transfers.extend(convert_block(data, trips))
        except InvalidBlockError as exc:
            print(str(exc))

    return converted_transfers


def group_trips(gtfs):
    unique_shapes = {}
    trips_by_block = {}

    for trip in sorted(gtfs.trips.values(),
                       key=lambda trip: trip.first_departure):
        if not trip.block_id:
            continue

        if len(gtfs.stop_times.get(trip.trip_id, [])) < 2:
            print(
                f'Warning: Trip {trip.trip_id} deleted as it has fewer than two stops.'
            )
            continue

        if config.InSeatTransfers.ignore_return_via_similar_trip:
            trip.shape_ref = unique_shapes.setdefault(trip.stop_shape,
                                                      trip.stop_shape)

        trips_by_block.setdefault(trip.block_id, []).append(trip)

    return trips_by_block


def may_convert_trips(gtfs, trips):
    if config.TripToTripTransfers.overwrite_existing:
        return True

    for trip in trips:
        transfers_out = gtfs.transfers.get(trip.trip_id)
        if not transfers_out:
            continue

        for transfer in transfers_out:
            if transfer.is_continuation:
                return False

    return True


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


class InvalidBlockError(ValueError):

    def __init__(self, trip, cont_trip, debug):
        super().__init__(self, 'Invalid block')
        self.trip = trip
        self.cont_trip = cont_trip
        self.debug = debug

    def __str__(self):
        wait_time = self.cont_trip.first_departure - self.trip.last_arrival
        block_id = self.trip.block_id

        return f'''
        Warning: Block {block_id} is invalid:
                {self.trip.first_departure} - {self.trip.last_arrival} [{self.trip.trip_id}]
                {self.cont_trip.first_departure} - {self.cont_trip.last_arrival} [{self.cont_trip.trip_id}]
                In two places at once for {abs(wait_time)} s on days {self.debug}.
        '''


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
    if wait_time < 0:
        if config.TripToTripTransfers.force_allow_invalid_blocks:
            return None
        else:
            debug = data.services.bdates(days_when_best)
            raise InvalidBlockError(trip_state.trip, cont_trip, debug)

    trip_state.days_to_match = trip_state.days_to_match.difference(
        days_when_best)
    trip_state.num_matches += 1

    return Transfer(from_trip_id=trip_state.trip.trip_id,
                    to_trip_id=cont_trip.trip_id,
                    _rank=trip_state.num_matches)
