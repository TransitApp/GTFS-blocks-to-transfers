"""
For each continuation identified by converting blocks, use heuristics to 
predict whether a transfer is most likely to be of type:

4: In-seat transfer
5: Vehicle continuation only (for operational reasons)
"""
from gtfs_loader.schema import DAY_SEC, TransferType
from . import config, shape_similarity


class ShapeMatchState:

    def __init__(self):
        self.shape_ptr_by_trip = {}
        self.shape_ptr_by_shape = {}
        self.similarity_by_shape_ptr = {}


def classify(gtfs, transfers):
    print('Predicting transfer_type for each identified continuation')
    shape_match = ShapeMatchState()
    for transfer in transfers:
        transfer.transfer_type = get_transfer_type(gtfs, shape_match, transfer)

    print(
        f'\tComparison by similarity metric required for {len(shape_match.shape_ptr_by_trip)} trips having {len(shape_match.shape_ptr_by_shape)} distinct stop_times shapes'
    )


def get_transfer_type(gtfs, shape_match, transfer):
    trip = gtfs.trips[transfer.from_trip_id]
    cont_trip = gtfs.trips[transfer.to_trip_id]

    wait_time = cont_trip.first_departure - trip.last_arrival
    if cont_trip.first_departure < trip.last_arrival:
        wait_time += DAY_SEC

    # transfer would require riders to wait for an excessively long time
    if wait_time > config.InSeatTransfers.max_wait_time:
        return TransferType.VEHICLE_CONTINUATION

    # transfer involves a banned stop
    if (trip.last_stop_time.stop.stop_name
            in config.InSeatTransfers.banned_stops or
            cont_trip.first_stop_time.stop.stop_name
            in config.InSeatTransfers.banned_stops):
        return TransferType.VEHICLE_CONTINUATION

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
