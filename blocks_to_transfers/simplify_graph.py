import collections
import types
from blocks_to_transfers import editor

from blocks_to_transfers.editor.schema import Transfer, TransferType
from blocks_to_transfers.service_days import DaySet


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
        return f'Node {self.trip_id} & {bin(self.days)[:-15:-1]}'

    def split(self, new_days):
        if new_days.issuperset(self.days):
            return Keep
        elif new_days.isdisjoint(self.days):
            return None
        
        new_days = new_days.intersection(self.days)
        self.days = self.days.difference(new_days)
        return Node(self.trip, new_days, self.in_edges.copy(), self.out_edges.copy())


def simplify(gtfs, services, generated_transfers):
    #add_fake_data(gtfs, services, generated_transfers)

    graph = Graph(gtfs, services)
    import_provided_transfers(graph)
    # TODO still
    # Test cases:
    # alternative routing [Translink]
    # vehicle coupling + vehicle splitting [VIA Rail Senneterre]
    # vehicle couple/splitting
    # vehicle couple + split with alternatives
    # simple cycles [Peoplemovers of some sort]
    # complex cycles
    # non disjoint broken examples
    # 
    # pytest 'driver'
    #
    # Cycle breaking
    # 1. Try to find and resolve them
    # 2. What does this do to visited state
    # 3. Warn that its best-efforts in super complex examples
    #
    # Backprop split needs to consider back_continuations!!!
    # We can probably split to_node along each in_edge almost
    # but then what? what's the point of this graph structure: basically every transfer has 0/1 in edge and 0/1 out edge
    #   propagation is still important and becomes messier
    #   vehicle split/couple still needs detection

    import_generated_transfers(graph, generated_transfers) 
    verify_constraints(graph)
    prohibited_nodes(graph)
    dfs_path(graph)
    #backprop_split(graph)
    #export_visit(graph)
    #dfs_exp(graph)

class StackCell:
    def __init__(self, node, days, parent) -> None:
        self.node = node
        self.days = days
        self.parent = parent

def ppath(cell):
    path = []
    path.append(cell.node.trip_id)
    while cell.parent:
        cell = cell.parent
        path.insert(0, cell.node.trip_id)

    return path

NilTrip = types.SimpleNamespace(trip_id='NIL')

def prohibited_nodes(graph):
    stack = collections.deque(graph.sources)
    visited = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue

        visited.add(node)

        to_days_remaining = node.days
        # Very similar to the block algo but also works on user-defined transfers
        for to_node in node.out_edges.keys():
            shift_days = -1 if to_node.trip.first_departure < node.trip.last_arrival else 0
            to_days_in_from_ref = to_node.days.shift(shift_days)
            to_days_remaining = to_days_remaining.difference(to_days_in_from_ref)
            stack.append(to_node)

        from_days_remaining = node.days
        for from_node in node.in_edges.keys():
            shift_days = 1 if node.trip.first_departure < from_node.trip.last_arrival else 0
            from_days_in_to_ref = from_node.days.shift(shift_days)
            from_days_remaining = from_days_remaining.difference(from_days_in_to_ref)
        
        if to_days_remaining:
            print(f'NIL out of {node.trip_id} on {graph.services.bdates(to_days_remaining)}')
            nil_node = Node(NilTrip, to_days_remaining, {node: NilTrip})
            graph.adjust(nil_node)

        if from_days_remaining:
            print(f'NIL into {node.trip_id} on {graph.services.bdates(from_days_remaining)}')
            nil_node = Node(NilTrip, from_days_remaining, {}, {node: NilTrip})
            graph.adjust(nil_node)
        graph.adjust(node)

def dfs_path(graph):
    stack = collections.deque(StackCell(node, node.days, None) for node in graph.sources)
    print(graph.sources)
    while stack:
        from_node = stack.pop()
        print(f'{ppath(from_node)}, days {graph.services.bdates(from_node.days)}')

        for to_node in from_node.node.out_edges:
            if from_node.node.trip is NilTrip or to_node.trip is NilTrip:
                shift_days = 0
            else:
                shift_days = -1 if to_node.trip.first_departure < from_node.node.trip.last_arrival else 0

            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = from_node.days.intersection(to_days_in_from_ref)
            # undo the shift on match days
            match_days = match_days.shift(-shift_days)

            if match_days:
                if to_node.trip is not NilTrip:
                    stack.append(StackCell(to_node, match_days, from_node))
                else:
                    print(f'\033[0;32m{ppath(from_node)}, last from_days was {graph.services.bdates(from_node.days)}' \
                        + f' to node claims to be {graph.services.bdates(to_node.days)}'
                        + f' days {graph.services.bdates(match_days)}\033[0m')



def dfs_exp(graph):  
     stack = collections.deque(StackCell(node, node.days, None) for node in graph.sources)

     while stack:
         from_node = stack.pop()
         #print(f'h {from_node.node.trip_id}')
         #print(f'Block = {ppath(from_node)}, Service = {graph.services.bdates(from_node.days)}')


         # 2. Consider all children on the current path 
         ok = False
         for to_node in from_node.node.out_edges:
            shift_days = -1 if to_node.trip.first_departure < from_node.node.trip.last_arrival else 0
            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = from_node.days.intersection(to_days_in_from_ref)
            if not match_days:
                continue

            from_but_not_to = from_node.days.difference(to_days_in_from_ref)
            to_but_not_from = to_days_in_from_ref.difference(from_node.days)
            print(f'''{from_node.node.trip_id} -> {to_node.trip_id}. 
            F+T: {graph.services.bdates(match_days)}
              F: {graph.services.bdates(from_but_not_to)}
              T: {graph.services.bdates(to_but_not_from)}
        ''')


            if match_days:
                stack.append(StackCell(to_node, match_days, from_node))
                ok = True
            if to_but_not_from:
                stack.append(StackCell(to_node, to_but_not_from, None))

            if from_but_not_to:
                ok = False

         # END OF BLOCK, prepare to export
         if ok:
            continue

         export_days = from_node.days
         print(f'If {graph.services.bdates(export_days)}')
         cell = from_node
         while cell:
            print(f'\t{cell.node.trip_id}')
            cell.node.days = cell.node.days.difference(export_days)
            cell = cell.parent
           


            


def import_provided_transfers(graph):
    for from_trip_id, transfers in graph.gtfs.transfers.items():
        if not from_trip_id:
            continue # Stop or route related transfers

        for transfer in transfers:
            if transfer.transfer_type not in {TransferType.IN_SEAT, TransferType.VEHICLE_CONTINUATION}:
                continue # Trip-to-trip transfers on separate vehicles
            
            if transfer.from_trip_id == transfer.to_trip_id:
                print(f'WARNING: Removed self-transfer for trip {transfer.from_trip_id}')
                continue
            
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

def verify_constraints(graph):
    queue = collections.deque(graph.sources)
    visited = set()

    while queue:
        node = queue.popleft()
        if node in visited:
            continue

        visited.add(node)
        is_valid = verify_distinct_cases(graph, node, 'preceding', node.in_edges.keys())
        is_valid = is_valid and verify_distinct_cases(graph, node, 'continuation', node.out_edges.keys())

        if not is_valid:
            pass
            # Delete the node and all connections

        for to_node in node.out_edges.keys():
            queue.append(to_node)

def verify_distinct_cases(graph, check_node, description, peer_nodes):
    union_cases = DaySet()
    distinct_cases = set()

    for peer_node in list(peer_nodes):
        if peer_node.days in distinct_cases:
            continue 

        if peer_node.days.isdisjoint(union_cases):
            union_cases = union_cases.union(peer_node.days)
            distinct_cases.add(peer_node.days)
            continue

        # FIXME: Shift magic is required

        conflict_days = ', '.join(str(date) for date in graph.services.to_dates(peer_node.days.intersection(union_cases)))
        other_trips = ', '.join(other_node.trip_id for other_node in peer_nodes if other_node is not peer_node)

        print(f'''
WARNING: Removed node for trip {check_node.trip_id} because its edges do not represent disjoint cases.
    Linked {description} trip {peer_node.trip_id} conflicts with other linked trips {other_trips} on the following days:
        {conflict_days}
''')
        return False

    return True

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


def export_visit(graph):
    services = graph.services
    stack = collections.deque(graph.sources)
    visited = set()

    graph.gtfs.transfers.clear()

    while stack:
        from_node = stack.pop()
        if from_node in visited:
            continue

        visited.add(from_node)
        from_trip_id = make_trip(graph, from_node)
        transfers_out = graph.gtfs.transfers.setdefault(from_trip_id, [])

        #print(f'{from_trip_id} {services.bdates(from_node.days)}:')
        for to_node, transfer in from_node.out_edges.items():
            to_trip_id = make_trip(graph, to_node)
            split_transfer = transfer.clone(
                from_trip_id=from_trip_id,
                to_trip_id=to_trip_id
            )
            #print(f'\t{split_transfer.from_trip_id},{split_transfer.to_trip_id},{split_transfer.transfer_type}')
            transfers_out.append(split_transfer)


            stack.append(to_node)

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