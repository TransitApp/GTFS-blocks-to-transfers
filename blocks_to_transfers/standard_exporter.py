import collections
from . import simplify_graph


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
            from_trip_id = simplify_graph.make_trip(graph, from_node)
            transfers_out = transfers.setdefault(from_trip_id, [])
            #print('=>',from_trip_id)

        for to_node, transfer in from_node.out_edges.items():
            if to_node.has_trip():
                 to_trip_id = simplify_graph.make_trip(graph, to_node)
                 #print('>>',to_trip_id)

            if from_node.has_trip() and to_node.has_trip():          
                split_transfer = transfer.clone(
                    from_trip_id=from_trip_id,
                    to_trip_id=to_trip_id
                )

                #print(f'{split_transfer.from_trip_id},{split_transfer.to_trip_id},{split_transfer.transfer_type}')
                transfers_out.append(split_transfer)
            stack.append(to_node)

    graph.gtfs.transfers = transfers

