import pprint
from collections import deque

from blocks_to_transfers.convert import wdates
from blocks_to_transfers.editor import duplicate
from blocks_to_transfers.editor.schema import Transfer, CalendarDate, ExceptionType
from blocks_to_transfers.editor.types import GTFSDate


def expand(data, transfers):
    print('Expanding trip-to-trip transfer DAG')
    G = graph_of_transfers(data, transfers)
    split_nodes(G)

    data.service_id_for_days = {frozenset(days): service_id for service_id, days in data.days_by_service.items()}
    data.num_split_services = 0
    export_graph(data, G)


class Graph:
    def __init__(self):
        self.sources = set()
        self.sinks = set()

    def adjust(self, node):
        if not node.in_edges:
            # NOTE: stretching the definition a bit to have isolated nodes appear here
            self.sources.add(node)
        elif not node.out_edges:
            self.sinks.add(node)
        else:
            self.sources.discard(node)
            self.sinks.discard(node)

    def del_edge(self, u, v):
        del u.out_edges[v]
        del v.in_edges[u]
        self.adjust(u)
        self.adjust(v)


class Node:
    def __init__(self, trip_id, days, in_edges=None, out_edges=None):
        self.trip_id = trip_id
        self.days = frozenset(days)
        self.in_edges = in_edges if in_edges is not None else {}
        self.out_edges = out_edges if out_edges is not None else {}
        self.visited = False

    def __eq__(self, other):
        return id(self) == id(other)

    def __hash__(self):
        return hash(id(self))

    def __repr__(self):
        return f'{self.trip_id} if {wdates(self.days)}'

    def split(self, days, edge):
        return Node(self.trip_id, days, self.in_edges.copy(), {edge[0]: edge[1]})


def graph_of_transfers(data, transfers):
    print('Identifying block sinks')

    node_of_trip = {}
    G = Graph()
    for transfer in transfers:
        v = get_node(data, node_of_trip, transfer.from_trip_id)
        w = get_node(data, node_of_trip, transfer.to_trip_id)
        v.out_edges[w] = transfer
        G.adjust(v)

        w.in_edges[v] = transfer
        G.adjust(w)

    return G


def get_node(data, node_of_trip, trip_id):
    node = node_of_trip.get(trip_id)
    if node:
        return node

    node = Node(trip_id, frozenset(data.days_by_service[data.gtfs.trips[trip_id].service_id]))
    node_of_trip[trip_id] = node
    return node


def split_nodes(G):
    print('Duplicating nodes')
    queue = deque(G.sinks)

    while queue:
        to_trip = queue.popleft()
        if to_trip.visited:
            continue

        to_trip.visited = True

        for from_trip, transfer in list(to_trip.in_edges.items()):
            # TODO: v.days needs to be 'adapted' back to w's service (+24 and also blocks continuing onto the next day)
            cont_days = to_trip.days & from_trip.days
            if not cont_days:
                # from and to trip never run on the same day; remove edge
                G.del_edge(from_trip, to_trip)
                continue

            # Days when from_trip operates but can't continue to to_trip
            residual_days = from_trip.days - to_trip.days
            if not residual_days:
                # If none, then graph doesn't require adjustment
                queue.append(from_trip)
                continue

            # Create a new node called from_trip_if_cont representing the case where from_trip -> to_trip is possible,
            # and link it to the other nodes in the graph.
            from_trip_if_cont = from_trip.split(cont_days, (to_trip, transfer))
            for from_from_trip, from_from_transfer in from_trip_if_cont.in_edges.items():
                from_from_trip.out_edges[from_trip_if_cont] = from_from_transfer

            G.adjust(from_trip_if_cont)
            to_trip.in_edges[from_trip_if_cont] = transfer
            queue.append(from_trip_if_cont)

            # Mutate from_trip, leaving it only the residual days where from_trip -> to_trip don't occur
            from_trip.days = residual_days
            G.del_edge(from_trip, to_trip)
            queue.append(from_trip)


def export_graph(data, G):
    """
    Export the continuation graph back to trip-to-trip transfers. Traversal is performed using depth-first search so as
    to output roughly a sequence of complete blocks, for ease of reading
    """
    transfers = []

    stack = list(G.sources)
    while stack:
        from_node = stack.pop()
        from_trip_id = instantiate_trip(data, from_node)

        for to_node, transfer_model in from_node.out_edges.items():
            to_trip_id = instantiate_trip(data, to_node)

            transfer = transfer_model.duplicate(
                from_trip_id=from_trip_id,
                to_trip_id=to_trip_id
            )

            transfers.append(transfer)
            stack.append(to_node)

    pprint.pprint(transfers)
    return transfers


def instantiate_trip(data, node):
    service_id = ensure_service(data, node.days)
    trip = data.gtfs.trips[node.trip_id]

    if node.days == data.days_by_service[trip.service_id]:
        specialized_trip_id = node.trip_id
    else:
        specialized_trip_id = f'{node.trip_id}_b2t:if_{service_id}'

    if specialized_trip_id not in data.gtfs.trips:
        print('Create', specialized_trip_id)
        trip.tombstone = True
        duplicate(data.gtfs.trips, node.trip_id, specialized_trip_id)
        duplicate(data.gtfs.stop_times, node.trip_id, specialized_trip_id)
        data.gtfs.trips[specialized_trip_id].service_id = service_id

    return specialized_trip_id

def ensure_service(data, days):
        days = frozenset(days)
        service_id = data.service_id_for_days.get(days)
        if service_id:
            return service_id
        return create_service_from_days(data, days)

def create_service_from_days(data, days):
        service_id = f'b2t:service_{data.num_split_services}'
        data.num_split_services += 1
        data.service_id_for_days[days] = service_id
        data.gtfs.calendar_dates[service_id] = [CalendarDate(
            service_id=service_id,
            date=GTFSDate(day),
            exception_type=ExceptionType.ADD
        ) for day in days]
        return service_id

 # TODO: split could create redundant nodes in the event of a real vehicle split (e.g. not all out edges
# disjoint)

# TODO: Tedious to implement but maybe we can fix cyclic blocks by finding connected components and making the last
#  trip of each block (i.e. closest to 23:59:59) arbitrarily a source node

# TODO: export:
#  - Check the pairing of the trip and the service day associated with each node.
#   - Same as the trip's real service? Do not modify trip, write transfer.
#   - Else, destroy the original trip and create copies
#       - Do those days already form a named service?
#       - If not, create a fake one for that name
#   - Problems: is there any redundancy between this process and convert? esp given that convert is front-to-back
#   - Can this algo create non-disjoint trip-variants? That is really bad and makes a mess in the UI.













