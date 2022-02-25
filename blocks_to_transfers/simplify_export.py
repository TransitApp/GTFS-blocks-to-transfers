import collections
from . import simplify_graph, editor


def export_visit(graph):
    """
    Export each node (trip) and edge (transfer) in the graph. Traversal is in DFS order
    from source nodes, followed by nodes forming cycles in arbitrary order. Any traversal
    order is valid, but this one was chosen for readability.

    A node might represent an existing trip, or it might represent a copy of a trip
    with a different set of days of service. A set of days of service might already 
    be associated with an existing service_id in the feed, or a new one can be created
    if needed.
    """
    stack = collections.deque(graph.nodes)
    stack.extend(graph.sources)
    visited = set()

    transfers = {}
    if '' in graph.gtfs.transfers:
        transfers[''] = graph.gtfs.transfers[''] # Preserve stop-to-stop transfers

    while stack:
        from_node = stack.pop()
        if from_node in visited:
            continue

        visited.add(from_node)
        if from_node.has_trip():
            from_trip_id = make_trip(graph, from_node)
            transfers_out = transfers.setdefault(from_trip_id, [])

        for to_node, transfer in from_node.out_edges.items():
            if to_node.has_trip():
                 to_trip_id = make_trip(graph, to_node)

            if from_node.has_trip() and to_node.has_trip():          
                split_transfer = transfer.clone(
                    from_trip_id=from_trip_id,
                    to_trip_id=to_trip_id
                )
                transfers_out.append(split_transfer)

            stack.append(to_node)

    graph.gtfs.transfers = transfers


def make_trip(graph, node):
    service_id = graph.services.get_or_assign(node.trip, node.days)

    if node.trip.service_id == service_id:
        # If the service_id did not change, avoid cloning the trip to minimize diffs
        return node.trip_id

    # Other trips are named according to a standard form
    split_trip_id = f'{node.trip_id}_b2t:if_{service_id}'
    if split_trip_id not in graph.gtfs.trips:
        editor.clone(graph.gtfs.trips, node.trip_id, split_trip_id)
        editor.clone(graph.gtfs.stop_times, node.trip_id, split_trip_id)
        graph.gtfs.trips[split_trip_id].service_id = service_id

    return split_trip_id
