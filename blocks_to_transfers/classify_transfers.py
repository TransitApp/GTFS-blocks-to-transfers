"""
For each continuation identified by converting blocks, use heuristics to 
predict whether a transfer is most likely to be of type:

4: In-seat transfer
5: Vehicle continuation only (for operational reasons)
"""
from .editor.schema import DAY_SEC, TransferType
from . import config, shape_similarity


def classify(gtfs, transfers):
    print('Predicting transfer_type for each identified continuation')
    unique_shapes = {
    }  # Used to merge identical sequences of stop_times from different trips
    shape_similarity_results = {
    }  # Used to cache Hausdorff metric calculations
    for transfer in transfers:
        transfer.transfer_type = get_transfer_type(gtfs, unique_shapes,
                                                   shape_similarity_results,
                                                   transfer)


def get_transfer_type(gtfs, unique_shapes, shape_similarity_results, transfer):
    trip = gtfs.trips[transfer.from_trip_id]
    cont_trip = gtfs.trips[transfer.to_trip_id]

    wait_time = cont_trip.first_departure - trip.last_arrival
    if cont_trip.first_departure < trip.last_arrival:
        wait_time += DAY_SEC

    # transfer would require riders to wait for an excessively long time
    if wait_time > config.InSeatTransfers.max_wait_time:
        return TransferType.VEHICLE_CONTINUATION

    # cont_trip resumes too far away from where trip ended (probably involves deadheading)
    if trip.last_point.distance_to(
            cont_trip.first_point
    ) > config.InSeatTransfers.same_location_distance:
        return TransferType.VEHICLE_CONTINUATION

    # trip and cont_trip form a full loop, therefore riders may want to stay
    # onboard despite similarity in shape.
    if (trip.first_point.distance_to(cont_trip.first_point) <
            config.InSeatTransfers.same_location_distance
            and trip.last_point.distance_to(cont_trip.last_point) <
            config.InSeatTransfers.same_location_distance):
        return TransferType.IN_SEAT

    if config.InSeatTransfers.ignore_return_via_same_route:
        if trip.route_id == cont_trip.route_id and trip.direction_id != cont_trip.direction_id:
            return TransferType.VEHICLE_CONTINUATION

    if config.InSeatTransfers.ignore_return_via_similar_trip:
        if not hasattr(trip, 'shape_ref'):
            trip.shape_ref = unique_shapes.setdefault(trip.stop_shape,
                                                      trip.stop_shape)

        if not hasattr(cont_trip, 'shape_ref'):
            cont_trip.shape_ref = unique_shapes.setdefault(
                cont_trip.stop_shape, cont_trip.stop_shape)

        if shape_similarity.trip_shapes_similar(shape_similarity_results,
                                                trip.shape_ref,
                                                cont_trip.shape_ref):
            return TransferType.VEHICLE_CONTINUATION

    # We presume that the rider will be able to stay onboard the vehicle
    return TransferType.IN_SEAT
