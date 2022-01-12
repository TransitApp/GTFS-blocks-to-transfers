"""
For every trip within a block, identifies valid continuation trips. Predicts whether each continuation is likely to be
an in-seat transfer, or simply a vehicle continuation for operational purposes.
"""
from datetime import timedelta
from . import config, shape_similarity
from .editor.schema import TransferType, Transfer, DAY_SEC

"""
TODO: 
1. test cases
3. readme
9. check if dupe trip -> dupe trip works correctly re:transfers
"""


def convert_blocks(data):
    print('Predicting continuations')
    converted_transfers = []

    del data.trips_by_block['brown_loop']
    for trips in data.trips_by_block.values():
        try:
            converted_transfers.extend(convert_block(data, trips))
        except InvalidBlockError as exc:
            print(str(exc))
            
    return converted_transfers


def convert_block(data, trips):
    converted_transfers = []

    for i_trip, trip in enumerate(trips):
        if not config.TripToTripTransfers.overwrite_existing and trip.trip_id in data.gtfs.transfers:
            converted_transfers.extend(data.gtfs.transfers[trip.trip_id])
            continue

        days_to_match = set(data.days_by_service[trip.service_id])
        shift_days = 1 if trip.shifted_to_next_day else 0
        any_matches = False

        try:
            for cont_trip in trips[i_trip + 1:]:
                transfer_opt = consider_transfer(data, days_to_match, trip, cont_trip, shift_days)
                if transfer_opt:
                    any_matches = True
                    converted_transfers.append(transfer_opt)

            # Search continues onto the next day; shift days of service from continuation trips back one day to match
            # the notation used to describe trip
            shift_days += 1

            for cont_trip in trips[:i_trip]:
                transfer_opt = consider_transfer(data, days_to_match, trip, cont_trip, shift_days)
                if transfer_opt:
                    any_matches = True
                    converted_transfers.append(transfer_opt)

        except StopIteration:
            # Will be raised once we know that there's no further trips to consider for transfers
            pass

        # If days_to_match is not empty, it results in an additional case where trip has no continuation on certain days
        # of service. We don't need to export this 'transfer' to transfers.txt but it must be taken into account when
        # duplicating trips.
        """
        if any_matches and days_to_match:
            converted_transfers.append(Transfer(
                transfer_type=TransferType.NOT_POSSIBLE,
                from_trip_id=trip.trip_id,
                to_trip_id=None,
                days_when_best=days_to_match
            ))
        """

    return converted_transfers


def pdates(dates):
    sdates = sorted(date.strftime('%m%d') for date in dates)
    tdates =  ', '.join(sdates[:14])
    if len(dates) > 14:
        tdates += ' ...'
    return tdates


def wdates(dates):
    sdates = sorted(date for date in dates)
    sdates = [date.strftime('%a') for date in sdates]
    tdates =  ', '.join(sdates[:14])
    if len(dates) > 14:
        tdates += ' ...'
    return tdates


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


def consider_transfer(data, days_to_match, trip, cont_trip, shift_days):
    wait_time = cont_trip.first_departure - trip.last_arrival

    if shift_days > 0:
        # Due to normalization of first departure time, the maximum shift needed is 24h to put the continuation trip
        # onto the previous service day
        wait_time += DAY_SEC

    # First check if cont_trip is a valid trip-to-trip transfer
    days_when_best = match_transfer(data, days_to_match, trip, wait_time, cont_trip, shift_days)
    if not days_when_best:
        return None

    return Transfer(
        transfer_type=classify_transfer(data, trip, wait_time, cont_trip),
        from_trip_id=trip.trip_id,
        to_trip_id=cont_trip.trip_id,
        # This field would allow us to immediately make the converted trip-to-trip transfers invariant of services,
        # but existing trip-to-trip transfers in this feed might also need to be split by cases, so we are required
        # to reconstruct this info anyway. (TODO: Field probably to be deleted...)
        days_when_best=days_when_best
    )


def match_transfer(data, days_to_match, trip, wait_time, cont_trip, shift_days):
    # transfer found for every day trip operates on
    if not days_to_match:
        raise StopIteration

    # Wait time too long even for operational purposes
    if wait_time > config.TripToTripTransfers.max_wait_time:
        raise StopIteration

    days_when_best = get_shifted_days_of_service(data.days_by_service, cont_trip, shift_days)
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


def get_shifted_days_of_service(days_by_service, trip, shift_days):
    if trip.shifted_to_next_day:
        shift_days -= 1

    # FIXME: Can this spuriously add extra days at the beginning of the service that were never intended?

    return {day + timedelta(days=shift_days) for day in days_by_service[trip.service_id]}


def classify_transfer(data, trip, wait_time, cont_trip):
    # transfer would require riders to wait for an excessively long time
    if wait_time > config.InSeatTransfers.max_wait_time:
        return TransferType.VEHICLE_CONTINUATION

    # cont_trip resumes too far away from where trip ended (probably involves deadheading)
    if trip.last_point.dist_to(cont_trip.first_point) > config.InSeatTransfers.same_location_distance:
        return TransferType.VEHICLE_CONTINUATION

    # trip and cont_trip form a loop, therefore any similarity in shape is not an issue for riders
    if (trip.first_point.dist_to(cont_trip.first_point) < config.InSeatTransfers.same_location_distance
        and trip.last_point.dist_to(cont_trip.last_point) < config.InSeatTransfers.same_location_distance):
        return TransferType.IN_SEAT

    if config.InSeatTransfers.ignore_return_via_same_route:
        if trip.route_id == cont_trip.route_id and trip.direction_id != cont_trip.direction_id:
            return TransferType.VEHICLE_CONTINUATION

    if config.InSeatTransfers.ignore_return_via_similar_trip:
        if shape_similarity.trip_shapes_similar(data.shape_similarity_results, trip.shape_ref, cont_trip.shape_ref):
            return TransferType.VEHICLE_CONTINUATION

    # We presume that the rider will be able to stay onboard the vehicle
    return TransferType.IN_SEAT


def add_transfers(gtfs, transfers):
    for transfer in transfers:
        if transfer.transfer_type == TransferType.NOT_POSSIBLE:
            continue

        gtfs.transfers.setdefault(transfer.from_trip_id, {})[transfer.to_trip_id] = transfer