# Controls whether two trips in a block will be interpreted as trip-to-trip transfers, or ignored
class TripToTripTransfers:
    # Maximum layover between a trip and its continuation
    max_wait_time = 1200  # seconds

    # If a block is invalid because it cannot be operated using a single vehicle, because a later trip departs before
    # the previous trip has completed, should the algorithm still attempt to find a plausible continuation trip?
    force_allow_invalid_blocks = False

    # If true, existing trip-to-trip transfers will be overwritten with predicted continuations from the algorithm
    overwrite_existing = False

    # If true, trip-to-trip transfers will be normalized such that for all of the days from_trip_id operates on, all of
    # the to_trip_ids are also in operation
    invariant_transfers = True


# Controls whether an identified continuation is marked as an in-seat transfer, where riders are permitted to stay
# onboard.
class InSeatTransfers:
    # Maximum wait time for riders aboard the vehicle. May be -1 if this agency never allows in-seat transfers.
    max_wait_time = 600  # seconds

    # Used to determine whether two stops are sufficiently close to be considered 'at the same location', needed for
    # a variety of heuristics.
    same_location_distance = 100  # meters

    # If true, ignore all trips serving the same route in the opposite direction
    ignore_return_via_same_route = False

    # If true, ignore all trips which appear to return along a similar path (determined by sequence of stop locations),
    # regardless of whether or not they are served by the same route
    ignore_return_via_similar_trip = True

    # Similarity of trips is predicted using a modified Hausdorff metric: are {similarity_percentile}% of the stops of
    # one trip within {similarity_distance} m of the other trip?
    #
    # The provided constants work best in urban areas, but are far from perfect even there.
    similarity_percentile = .8  # / 1.0
    similarity_distance = 500  # meters



