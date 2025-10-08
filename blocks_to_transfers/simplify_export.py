import collections
import gtfs_loader


def export_visit(graph, itineraries=False):
    """
    Export each node (trip) and edge (transfer) in the graph. 

    A node might represent an existing trip, or it might represent a copy of a trip
    with a different set of days of service. A set of days of service might already 
    be associated with an existing service_id in the feed, or a new one can be created
    if needed.

    Transfers not relating to trip continuations are preserved and updated.
    """
    print('Exporting continuation graph')
    stack = collections.deque(graph.nodes)
    visited = set()
    trip_id_splits = {}
    transfers = gtfs_loader.types.EntityDict(
        fields=graph.gtfs.transfers._resolved_fields)

    # Keep stop-to-stop transfers is the feed uses them
    transfers[''] = graph.gtfs.transfers.get('', [])

    while stack:
        from_node = stack.pop()
        if from_node in visited:
            continue

        visited.add(from_node)
        if from_node.has_trip():
            from_trip_id = make_trip(graph, trip_id_splits, from_node, itineraries=itineraries)
            transfers_out = transfers.setdefault(from_trip_id, [])

        for to_node, transfer in from_node.out_edges.items():
            if to_node.has_trip():
                to_trip_id = make_trip(graph, trip_id_splits, to_node, itineraries=itineraries)

            if from_node.has_trip() and to_node.has_trip():
                split_transfer = transfer.clone(from_trip_id=from_trip_id,
                                                to_trip_id=to_trip_id)
                transfers_out.append(split_transfer)

            stack.append(to_node)

    delete_fully_split_trips(graph.gtfs, trip_id_splits, itineraries=itineraries)
    split_noncontinuation_transfers(graph.gtfs, trip_id_splits, transfers)
    graph.gtfs.transfers = transfers


def split_noncontinuation_transfers(gtfs, trip_id_splits, transfers):
    """
    GTFS also supports trip-to-trip transfers for trips operated by separate
    vehicles. These transfers apply to every split variant of a particular trip.
    """
    for from_trip_id, predef_transfers in gtfs.transfers.items():
        if not from_trip_id:
            continue

        for transfer in predef_transfers:
            if transfer.is_continuation:
                continue

            for split_from_trip_id in trip_id_splits.get(
                    from_trip_id, {from_trip_id}):
                transfers_out = transfers.setdefault(split_from_trip_id, [])

                for split_to_trip_id in trip_id_splits.get(
                        transfer.to_trip_id, {transfer.to_trip_id}):
                    split_transfer = transfer.clone(
                        from_trip_id=split_from_trip_id,
                        to_trip_id=split_to_trip_id)
                    transfers_out.append(split_transfer)


def make_trip(graph, trip_id_splits, node, itineraries=False):
    splits = trip_id_splits.setdefault(node.trip_id, set())

    trip_original_days = graph.services.days_by_trip(node.trip)
    if trip_original_days == node.days:
        # If the days of service did not change, avoid cloning the trip to minimize diffs
        splits.add(node.trip_id)
        return node.trip_id

    # Other trips are named according to a standard form
    service_id = graph.services.get_or_assign(node.trip, node.days)
    split_trip_id = f'{node.trip_id}_b2t:if_{service_id}'
    if split_trip_id not in graph.gtfs.trips:
        gtfs_loader.clone(graph.gtfs.trips, node.trip_id, split_trip_id)
        # The trip will follow the same itinerary, no need to clone the itinerary
        if not itineraries:
            gtfs_loader.clone(graph.gtfs.stop_times, node.trip_id, split_trip_id)
        graph.gtfs.trips[split_trip_id].service_id = service_id

    splits.add(split_trip_id)
    return split_trip_id


def delete_fully_split_trips(gtfs, trip_id_splits, itineraries=False):
    """
    If a particular trip has been split into variants, remove the now-redundant
    original trip.
    """
    for trip_id in list(gtfs.trips.keys()):
        if trip_id not in trip_id_splits:
            continue

        if trip_id in trip_id_splits[trip_id]:
            continue

        del gtfs.trips[trip_id]
        if not itineraries:
            del gtfs.stop_times[trip_id]
