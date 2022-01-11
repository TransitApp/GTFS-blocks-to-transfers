from collections import deque

from blocks_to_transfers.convert import wdates


class Node:
    def __init__(self, trip_id, days, edges=None):
        self.trip_id = trip_id
        self.days = frozenset(days)
        self.edges = edges if edges is not None else []
        self.visited = False

    def __eq__(self, other):
        return self.trip_id == other.trip_id and self.days == other.days

    def __hash__(self):
        return hash((self.trip_id, self.days))

    def __repr__(self):
        return f'{self.trip_id} if {wdates(self.days)}'

    def split(self, days):
        return Node(self.trip_id, days, self.edges.copy())


def get_node(data, node_of_trip, trip_id):
    node = node_of_trip.get(trip_id)
    if node:
        return node

    node = Node(trip_id, frozenset(data.days_by_service[data.gtfs.trips[trip_id].service_id]))
    node_of_trip[trip_id] = node
    return node


def expand(data, transfers):
    print('Expanding trip-to-trip transfer DAG')
    print('Identifying block sinks')
    node_of_trip = {}
    nodes_with_out_edges = set()
    nodes_with_in_edges = set()
    for transfer in transfers:
        v = get_node(data, node_of_trip, transfer.to_trip_id)
        w = get_node(data, node_of_trip, transfer.from_trip_id)
        v.edges.append((w, transfer))
        nodes_with_out_edges.add(v)
        nodes_with_in_edges.add(w)

    source_nodes = nodes_with_out_edges - nodes_with_in_edges

    # TODO: Tedious to implement but maybe we can fix cyclic blocks by finding connected components and making the last
    #  trip of each block (i.e. closest to 23:59:59) arbitrarily a source node

    print('Duplicating nodes')
    q = deque(source_nodes)
    while q:
        v = q.popleft()
        if v.visited:
            continue

        v.visited = True
        new_edges = []
        for w, e in v.edges:
            # TODO: v.days needs to be 'adapted' back to w's service (+24 and also blocks continuing onto the next day)

            vw_days = v.days & w.days
            if not vw_days:
                continue

            xw_days = w.days - v.days
            if not xw_days:
                new_edges.append((w, e))
                q.append(w)
                continue

            # TODO: split could create redundant nodes in the event of a real vehicle split (e.g. not all out edges
            # disjoint)
            vw = w.split(vw_days)
            if vw.edges:
                nodes_with_out_edges.add(vw)

            new_edges.append((vw, e))
            q.append(vw)

            w.days = xw_days
            # TODO: Does w really need to be enqueued? yes - it may have become a source node....
            q.append(w)

        v.edges = new_edges

    # ALSO Need to export edgeless nodes
    # Does vdays != wdays ever?
    # yes.... diamond
    export_stack = list(nodes_with_out_edges)
    while export_stack:
        v = export_stack.pop()
        for w, transfer in v.edges:
            print((w.trip_id, v.trip_id, int(transfer.transfer_type), wdates(v.days), wdates(w.days)))

    # TODO: export:
    #  - visit the block, maybe even from source-to-sink if it makes the outputted order more normal looking
    #  - Check the pairing of the trip and the service day associated with each node.
    #   - Same as the trip's real service? Do not modify trip, write transfer.
    #   - Else, destroy the original trip and create copies
    #       - Do those days already form a named service?
    #       - If not, create a fake one for that name
    #   - Problems: is there any redundancy between this process and convert? esp given that convert is front-to-back
    #   - Can this algo create non-disjoint trip-variants? That is really bad and makes a mess in the UI.













