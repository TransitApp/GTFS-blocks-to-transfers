"""
Before exporting transfers, we use a very flexible graph structure to model the interactions
between trips, verify conditions and transform the representation.
"""
import collections
import enum
from .editor.schema import Transfer, TransferType
from . import service_days

class Graph:
    def __init__(self, gtfs, services):
        self.gtfs = gtfs
        self.services = services
        self.sources = set()
        self.sinks = set()
        self.nodes = []
        self.primary_nodes = {}


    def add(self, *args, **kwargs):
        return self.add_node(Node(*args, **kwargs))


    def add_node(self, node):
        self.nodes.append(node)
        self.nodes.append(node.source_node)
        self.nodes.append(node.sink_node)
        return node

    def make_primary_node(self, trip_id):
        node = self.primary_nodes.get(trip_id)
        if node:
            return node
    
        trip = self.gtfs.trips[trip_id]
        node = self.primary_nodes[trip_id] = self.add(trip, self.services.days_by_trip(trip))
        return node

    def make_primary_edge(self, transfer):
        from_node = self.make_primary_node(transfer.from_trip_id)
        to_node = self.make_primary_node(transfer.to_trip_id)
        from_node.out_edges[to_node] = to_node.in_edges[from_node] = transfer

        return from_node, to_node


    def del_edge(self, from_node, to_node):
        del from_node.out_edges[to_node]
        del to_node.in_edges[from_node]


    def split(self, target_node, from_node, to_node, days):
        """
        Take target_node and make a new node representing a subset of its days 
        of operation. The new node has all the connections the previous node did,
        except that it replaces the connection between from_node and to_node.

        It is also possible that the subset represents no days at all, in 
        which case the connection between from_node and to_node is removed.

        Finally, target_node may already be suitable and might not be modifed.
        """
        node_split = target_node.split(days)
        if node_split is Keep:
            return node_split
        

        self.del_edge(from_node, to_node)

        if node_split:
            self.add_node(node_split)

        return node_split


Keep = object()

class BaseNode:
    def __init__(self, days, in_edges, out_edges):
        self.days = days if days else service_days.DaySet()
        self.in_edges = in_edges 
        self.out_edges = out_edges 
        self.vehicle_join = False
        self.vehicle_split = False

        for in_node, edge in self.in_edges.items():
            in_node.out_edges[self] = edge

        for out_node, edge in self.out_edges.items():
            out_node.in_edges[self] = edge

    def has_trip(self):
        return False

    @property
    def trip_id(self):
        return '<no trip>'


class Node(BaseNode):
    def __init__(self, trip, days, in_edges=None, out_edges=None):
        in_edges = in_edges or {}
        out_edges = out_edges or {}
        super().__init__(days, in_edges, out_edges)

        self.source_node = BaseNode(service_days.DaySet(), {}, {self: None})
        self.sink_node = BaseNode(service_days.DaySet(), {self: None}, {})
        self.trip = trip
    


    def has_trip(self):
        return True


    @property
    def trip_id(self):
        return self.trip.trip_id


    def split(self, new_days):
        if new_days.issuperset(self.days):
            return Keep
        elif new_days.isdisjoint(self.days):
            return None
        
        new_days = new_days.intersection(self.days)
        self.days = self.days.difference(new_days)
        return Node(self.trip, new_days, self.in_edges.copy(), self.out_edges.copy())


def simplify(gtfs, services, generated_transfers):
    graph = Graph(gtfs, services)
   
    add_fake_data(gtfs, services, generated_transfers)
    import_generated_transfers(graph, generated_transfers)
    split_ordered_alternatives(graph)
    delete_impossible_edges(graph, print_warnings=False)
    
    import_predefined_transfers(graph)
    delete_impossible_edges(graph, print_warnings=True)
    validate(graph)
    return graph


def import_predefined_transfers(graph):
    for from_trip_id, transfers in graph.gtfs.transfers.items():
        if not from_trip_id:
            continue # route-to-route or stop-to-stop transfers and such

        for transfer in transfers:
            if transfer.from_trip_id == transfer.to_trip_id:
                print(f'WARNING: Removed self-transfer for trip {transfer.from_trip_id}')
                continue
            
            graph.make_primary_edge(transfer)


def import_generated_transfers(graph, generated_transfers):
    for transfer in generated_transfers:
        graph.make_primary_edge(transfer)


def split_ordered_alternatives(graph):
    """
    The spec requires all from_trip_ids of a certain to_trip_id, and all to_trip_ids of a certain from_trip_id,
    to form 'disjoint cases' (either matching another case exactly, or disjoint of all cases.)

    For transfers automatically generated by conversion from blocks, there is a rule we can use to fix
    cases that aren't disjoint: greedily take as many days as possible from each transfer in order of wait_time.

    (For user-defined transfers, there's no way to know if the conflicting 
    trips are alternatives, or vehicle joins/splits, or both.)

    This step splits primary nodes into separate nodes for each cases. For convenience of traversal over newly created
    nodes, we use BFS but any traversal order is valid. This step repeats roughly the same calculation as convert_blocks,
    but nodes can be split several times in a row in this operation.
    """
    queue = collections.deque(graph.nodes)
    visited = set()
    while queue:
        from_node = queue.popleft()
        if from_node in visited:
            continue

        visited.add(from_node)
        days_running = from_node.days
        days_matched = service_days.DaySet()

        for to_node, transfer in list(from_node.out_edges.items()):
            if not transfer or not transfer.is_continuation:
                continue

            to_days_in_frame = graph.services.days_in_from_frame(from_node.trip, to_node.trip, to_node.days)
            days_when_best = to_days_in_frame.intersection(days_running)

            if not days_when_best.isdisjoint(days_matched):
                days_when_best = days_when_best.difference(days_matched)
                to_node_split = graph.split(to_node, from_node, to_node, days_when_best)
                queue.append(to_node_split)

            days_matched = days_matched.union(days_when_best)
            queue.append(to_node)
        

def delete_impossible_edges(graph, print_warnings):
    """
    Delete any edges that can never be crossed, because there are no common 
    days of service between from_node and to_node. 

    We use it silently to clean up after transforms of converted blocks,
    and with warnings to help users fix predefined transfers.txt entries
    that are not useful.
    """

    for from_node in graph.nodes:
        if not from_node.has_trip():
            continue


        for to_node, transfer in list(from_node.out_edges.items()):
            if not to_node.has_trip(): # sink_node is permanent 
                continue

            if not transfer.is_continuation:
                continue

            to_node_days = graph.services.days_in_from_frame(from_node.trip, to_node.trip, to_node.days)
            match_days = to_node_days.intersection(from_node.days)
            if not match_days:
                if print_warnings:
                    print(f'WARNING: Removing {from_node.trip_id} -> {to_node.trip_id} as it does not occur on any days of service.')
                graph.del_edge(from_node, to_node)


class EdgeType(enum.Enum):
    IN = 0
    OUT = 1


def validate(graph):
    """
    The spec requires all from_trip_ids of a certain to_trip_id, and all 
    to_trip_ids of a certain from_trip_id, to form 'disjoint cases' (either 
    matching another case exactly, or disjoint of all cases.) This step deletes
    non-conformant edges.

    For any node, if there is no out-edge continuation on a certain day, it is 
    associated with the imaginary 'start node'. Similarily, if there are no
    in-edges for a certain day, it will be associated with the 'terminal node'.
    """
    for node in graph.nodes:
        if not node.has_trip():
            continue

        has_joining = validate_distinct_cases(graph, EdgeType.IN, node, node.in_edges)
        if has_joining:
            node.vehicle_join = True

        has_splitting = validate_distinct_cases(graph, EdgeType.OUT, node, node.out_edges)
        if has_splitting:
            node.vehicle_split = True


def validate_distinct_cases(graph, edge_type, node, neighbours):
    union_cases = service_days.DaySet()
    distinct_cases = set()
    has_join_split = False

    for neighbour, transfer in list(neighbours.items()):
        if not neighbour.has_trip() or not transfer.is_continuation:
            continue # Regular transfers between trips that don't share vehicles; these criteria do not apply

        if edge_type is EdgeType.OUT:
            match_days = graph.services.days_in_from_frame(node.trip, neighbour.trip, neighbour.days)
        else:
            match_days = graph.services.days_in_to_frame(neighbour.trip, node.trip, neighbour.days)

        if match_days in distinct_cases:
            has_join_split = True
            continue 

        if match_days.isdisjoint(union_cases):
            union_cases = union_cases.union(match_days)
            distinct_cases.add(match_days)
            continue

        conflict_days = ', '.join(str(date) for date in graph.services.to_dates(match_days.intersection(union_cases)))
        conflict_days = graph.services.bdates(match_days.intersection(union_cases))
        other_trips = ', '.join(other_node.trip_id for other_node in neighbours if other_node is not neighbour)

        if edge_type is EdgeType.OUT:
            print(f'WARNING: Removing {node.trip_id} [*] -> {neighbour.trip_id} as it does not represent a disjoint case.')
            graph.del_edge(node, neighbour)
        else:
            print(f'WARNING: Removing {neighbour.trip_id} -> {node.trip_id} [*] as it does not represent a disjoint case.')
            graph.del_edge(neighbour, node)

        print(f'\tConflict with other trips ({other_trips}) on {conflict_days}\n')

    residual_days = node.days.difference(union_cases)
    if residual_days:
        if edge_type is EdgeType.OUT:
            node.sink_node.days = node.sink_node.days.union(residual_days)
            graph.sinks.add(node.sink_node)
        else:
            node.source_node.days = node.source_node.days.union(residual_days)
            graph.sources.add(node.source_node)

    return has_join_split

 
def add_fake_data(gtfs, services, generated_transfers):
     # For testing inject some fake transfers
    generated_transfers.append(Transfer(
        from_trip_id='ws_1',
        to_trip_id='ws_2',
        transfer_type=TransferType.VEHICLE_CONTINUATION,
        _partial_days=False,
        _days_when_best=(services.days_by_trip(gtfs.trips['ws_2'])
            .intersection(services.days_by_trip(gtfs.trips['ws_1'])))
    ))

    generated_transfers.append(Transfer(
        from_trip_id='ws_1',
        to_trip_id='vs_3',
        transfer_type=TransferType.VEHICLE_CONTINUATION,
        _partial_days=True,
        _days_when_best=(services.days_by_trip(gtfs.trips['vs_3'])
            .difference(services.days_by_trip(gtfs.trips['ws_2']))
            .intersection(services.days_by_trip(gtfs.trips['ws_1'])))
    ))
