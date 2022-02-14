import collections

from blocks_to_transfers.editor.schema import Transfer

class Graph:
    def __init__(self, gtfs, services) -> None:
        self.gtfs = gtfs
        self.services = services
        self.sources = set()
        self.sinks = set()
        self.primary_nodes = {}

    def adjust(self, node):
        if not node or node is Keep:
            return 

        if not node.in_edges:
            # Isolated nodes are considered sources
            self.sources.add(node)
        elif not node.out_edges:
            self.sinks.add(node)
        else:
            self.sources.discard(node)
            self.sinks.discard(node)

    
    def primary_node(self, trip_id):
        node = self.primary_nodes.get(trip_id)
        if node:
            return node
    
        trip = self.gtfs.trips[trip_id]
        node = self.primary_nodes[trip_id] = Node(trip, self.services.days_by_trip(trip))
        return node

    def primary_edge(self, transfer):
        from_node = self.primary_node(transfer.from_trip_id)
        to_node = self.primary_node(transfer.to_trip_id)
        from_node.out_edges[to_node] = to_node.in_edges[from_node] = transfer

        self.adjust(from_node)
        self.adjust(to_node)
        return from_node, to_node

    def split(self, target_node, from_node, to_node, days):
        node_split = target_node.split(days)
        if node_split is Keep:
            return node_split

        del from_node.out_edges[to_node]
        del to_node.in_edges[from_node]

        self.adjust(from_node)
        self.adjust(to_node)
        self.adjust(node_split)
        return node_split


Keep = object()

class Node:
    def __init__(self, trip, days, in_edges=None, out_edges=None) -> None:
        self.trip = trip
        self.days = days
        self.in_edges = in_edges or {}
        self.out_edges = out_edges or {}

        for in_node, edge in self.in_edges.items():
            in_node.out_edges[self] = edge

        for out_node, edge in self.out_edges.items():
            out_node.in_edges[self] = edge

    @property
    def trip_id(self):
        return self.trip.trip_id

    def __repr__(self) -> str:
        return '???'

    def split(self, new_days):
        if new_days.issuperset(self.days):
            return Keep
        elif new_days.isdisjoint(self.days):
            return None
        
        new_days = new_days.intersection(self.days)
        self.days = self.days.difference(new_days)
        return Node(self.trip, new_days, self.in_edges.copy(), self.out_edges.copy())

def convert(gtfs, services, generated_transfers):
    # For testing inject some fake transfers
    generated_transfers.append(Transfer(
        from_trip_id='ws_1',
        to_trip_id='ws_2',
        _partial_days=False,
        _days_when_best=(services.days_by_trip(gtfs.trips['ws_2'])
            .intersection(services.days_by_trip(gtfs.trips['ws_1'])))
    ))

    generated_transfers.append(Transfer(
        from_trip_id='ws_1',
        to_trip_id='vs_3',
        _partial_days=True,
        _days_when_best=(services.days_by_trip(gtfs.trips['vs_3'])
            .difference(services.days_by_trip(gtfs.trips['ws_2']))
            .intersection(services.days_by_trip(gtfs.trips['ws_1'])))
    ))

    graph = Graph(gtfs, services)
    import_provided_transfers(graph, gtfs)
    import_generated_transfers(graph, generated_transfers)
    backprop_split(graph)
    export_visit(graph, services)
    

def import_provided_transfers(graph, gtfs):
    for transfers in gtfs.transfers.values():
        for transfer in transfers:
           graph.primary_edge(transfer)

def import_generated_transfers(graph, generated_transfers):
    for transfer in generated_transfers:
        from_node, to_node = graph.primary_edge(transfer)

        if getattr(transfer, '_partial_days', False):
            to_node_split = graph.split(to_node, from_node, to_node, transfer._days_when_best)
            if to_node_split is Keep:
                desc = 'Keep'
            elif not to_node_split:
                desc = 'Delete'
            else:
                desc = 'Modify'

            print(desc, from_node.trip_id, '->', to_node.trip_id, 
                'limit', graph.services.bdates(transfer._days_when_best), 'split', graph.services.bdates(to_node.days))

def backprop_split(graph):
    queue = collections.deque(graph.sinks)
    visited = set()

    while queue:
        to_node = queue.popleft()
        if to_node in visited:
            continue

        visited.add(to_node)
        for from_node in list(to_node.in_edges.keys()):
            shift_days = -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0
            to_days_in_from_ref = to_node.days.shift(shift_days)
            from_node_split = graph.split(from_node, from_node, to_node, to_days_in_from_ref)

            if from_node_split is Keep:
                queue.append(from_node)
                continue

            if from_node_split:
                queue.append(from_node_split)
            
            if from_node in graph.sinks:
                queue.append(from_node)


def export_visit(graph, services):
    stack = collections.deque(graph.sources)
    visited = set()

    while stack:
        from_node = stack.pop()
        if from_node in visited:
            continue

        visited.add(from_node)
        print(from_node.trip_id, services.bdates(from_node.days))
        for to_node, transfer in from_node.out_edges.items():
            print('\t->', to_node.trip_id, services.bdates(to_node.days))
            stack.append(to_node)