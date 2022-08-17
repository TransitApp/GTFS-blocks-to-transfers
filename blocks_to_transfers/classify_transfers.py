"""
For each continuation identified by converting blocks, use heuristics to 
predict whether a transfer is most likely to be of type:

4: In-seat transfer
5: Vehicle continuation only (for operational reasons)
"""
import collections
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from gtfs_loader.schema import DAY_SEC, TransferType
from . import config, shape_similarity


class Operation(str, Enum):
    # Change the transfer_type
    MODIFY = "modify"

    # Not implemented: add blocks to specific trips
    CREATE_BLOCK = "create_block"

    # Not implemented: entirely remove a trip-to-trip transfers
    REMOVE = "remove"


class ShapeMatchState:

    def __init__(self):
        self.shape_ptr_by_trip = {}
        self.shape_ptr_by_shape = {}
        self.similarity_by_shape_ptr = {}


def classify(gtfs, transfers):
    print('Predicting transfer_type for each identified continuation')
    shape_match = ShapeMatchState()
    rule_stats = collections.Counter()

    for transfer in transfers:
        transfer.transfer_type = get_transfer_type(gtfs, shape_match, rule_stats, transfer)

    print(
        f'\tComparison by similarity metric required for {len(shape_match.shape_ptr_by_trip)} trips having {len(shape_match.shape_ptr_by_shape)} distinct stop_times shapes'
    )
    print_rule_stats(rule_stats)


def get_transfer_type(gtfs, shape_match, rule_stats, transfer):
    trip = gtfs.trips[transfer.from_trip_id]
    cont_trip = gtfs.trips[transfer.to_trip_id]

    wait_time = cont_trip.first_departure - trip.last_arrival
    if cont_trip.first_departure < trip.last_arrival:
        wait_time += DAY_SEC

    # transfer would require riders to wait for an excessively long time
    if wait_time > config.InSeatTransfers.max_wait_time:
        return TransferType.VEHICLE_CONTINUATION

    specified_type = get_specific_cases_result(rule_stats, trip, cont_trip)
    # a specific rule governs the type of this transfer
    if specified_type is not None:
        return specified_type

    # cont_trip resumes too far away from where trip ended (probably involves deadheading)
    if trip.last_point.distance_to(
            cont_trip.first_point
    ) > config.InSeatTransfers.same_location_distance:
        return TransferType.VEHICLE_CONTINUATION

    # trip and cont_trip form a full loop, so riders may want to stay
    # onboard despite similarity in shape.
    if (trip.first_point.distance_to(cont_trip.first_point) <
            config.InSeatTransfers.same_location_distance and
            trip.last_point.distance_to(cont_trip.last_point) <
            config.InSeatTransfers.same_location_distance):
        return TransferType.IN_SEAT

    if config.InSeatTransfers.ignore_return_via_same_route:
        if trip.route_id == cont_trip.route_id and trip.direction_id != cont_trip.direction_id:
            return TransferType.VEHICLE_CONTINUATION

    if config.InSeatTransfers.ignore_return_via_similar_trip:
        if shape_similarity.trip_shapes_similar(
                shape_match.similarity_by_shape_ptr,
                get_shape_ptr(shape_match, trip),
                get_shape_ptr(shape_match, cont_trip)):
            return TransferType.VEHICLE_CONTINUATION

    # We presume that the rider will be able to stay onboard the vehicle
    return TransferType.IN_SEAT


def get_shape_ptr(shape_match, trip):
    """
    For a given trip, we first check if we've already found a representative 
    for its shape. If so, we return that pointer.

    For trips not previously encountered, we hash its shape to determine if a
    representative is already set for that shape. If so, we return that 
    pointer.

    Otherwise, we use the trip's stop_shape object as the representative and 
    later trips sharing the same shape will point to it.
    """

    shape_ptr = shape_match.shape_ptr_by_trip.get(trip.trip_id)

    if shape_ptr:
        return shape_ptr

    shape_ptr = shape_match.shape_ptr_by_shape.setdefault(
        trip.stop_shape, trip.stop_shape)
    shape_match.shape_ptr_by_trip[trip.trip_id] = shape_ptr
    return shape_ptr


def get_specific_cases_result(rule_stats, trip, cont_trip):
    """
    Last matching rule wins. 
    Returns None if no specific rule applies. Heuristics will be used in that case.
    """
    last_idx, last_specified_type = None, None

    for i, rule in enumerate(config.SpecialContinuations):
        specified_type = apply_specific_case(rule, trip, cont_trip)

        if specified_type is not None:
            last_idx, last_specified_type = i, specified_type

    if last_idx is not None:
       rule_stats[last_idx] += 1

    return last_specified_type


def apply_specific_case(rule, trip, cont_trip):
    if rule.op is not None and rule.op != Operation.MODIFY:
        # Other operations not yet implemented
        return None

    for selector in rule.match:
        if selector_applies_to_trips(selector, trip, cont_trip):
            return TransferType(rule.transfer_type)


@dataclass
class StandardSelector:
    route: Optional[str] = None
    stop: Optional[str] = None

    def applies(self, trip, stop_to_check):
        if self.route is None and self.stop is None:
            # Has no criteria; probably a bug
            return False

        if self.route is not None and self.route != trip.route.route_short_name:
            return False

        if self.stop is not None and self.stop != stop_to_check.stop_name:
            return False

        return True


def selector_applies_to_trips(selector, trip, cont_trip):
    if selector.all:
        # "all" selectors always apply
        return True

    if selector.through:
        # "through" selectors apply if they match either trip or cont_trip
        std_selector = StandardSelector(**selector.through)
        return (std_selector.applies(trip, trip.last_stop)
                or std_selector.applies(cont_trip, cont_trip.first_stop))

    if not selector['from'] and not selector.to:
        # Doesn't have any valid selectors
        return False

    if selector['from']:
        std_selector = StandardSelector(selector['from'].route, selector['from'].last_stop)
        if not std_selector.applies(trip, trip.last_stop):
            return False

    if selector.to:
        std_selector = StandardSelector(selector.to.route, selector.to.first_stop)
        if not std_selector.applies(cont_trip, cont_trip.first_stop):
            return False

    return True


def print_rule_stats(rule_stats):
    if not rule_stats:
        return

    print('\tSpecial continuation rules by number of matches')
    for idx, freq in rule_stats.most_common():
        print(f'\t\t{freq: 4d} {config.SpecialContinuations[idx]}')

