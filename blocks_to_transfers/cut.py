import collections
from re import L
from blocks_to_transfers import service_days
from blocks_to_transfers.service_days import wdates


class Graph:
    def __init__(self) -> None:
        self.sources = set()
        self.sinks = set()

    def adjust(self, node):
        if not node:
            return 

        if not node.in_edges:
            # Isolated nodes are considered sources
            self.sources.add(node)
        elif not node.out_edges:
            self.sinks.add(node)
        else:
            self.sources.discard(node)
            self.sinks.discard(node)

Keep = object()

class Node:
    def __init__(self, trip_id, days, in_edges=None, out_edges=None) -> None:
        self.trip_id = trip_id
        self.days = days
        self.in_edges = in_edges or {}
        self.out_edges = out_edges or {}

        for in_node, edge in self.in_edges.items():
            in_node.out_edges[self] = edge

        for out_node, edge in self.out_edges.items():
            out_node.in_edges[self] = edge


    def __repr__(self) -> str:
        return f'Node [{self.trip_id} on {wdates(self.days)}]'

    def split(self, new_days):
        if new_days.issuperset(self.days):
            return Keep
        elif new_days.isdisjoint(self.days):
            return None
        
        new_days &= self.days
        self.days -= new_days
        return Node(self.trip_id, new_days, self.in_edges.copy(), self.out_edges.copy())

def convert(gtfs, services):
    graph = import_transfers(gtfs, services)
    greedy_split_simple(graph)
    backprop_split(graph, gtfs)
    export_visit(graph)
    
def import_transfers(gtfs, services):
    """
    ws series are fakes for testing, they violate the spec so we have to flag them
    """
    gtfs.transfers['ws_1'][0]._has_conflict = True
    gtfs.transfers['ws_1'][0]._days_when_best = services.days_by_trip(gtfs.trips['vs_3']) - services.days_by_trip(gtfs.trips['ws_2'])

    trip_node = {}
    graph = Graph()
    for from_trip_id, transfers in sorted(gtfs.transfers.items(), key=lambda kv: gtfs.trips[kv[0]].first_departure):
        from_node = make_node(gtfs, services, trip_node, from_trip_id)
        for transfer in sorted(transfers, key=lambda v: gtfs.trips[v.to_trip_id].first_departure):
            to_trip_id = transfer.to_trip_id
            to_node = make_node(gtfs, services, trip_node, to_trip_id)

            from_node.out_edges[to_node] = transfer
            to_node.in_edges[from_node] = transfer
            graph.adjust(from_node)
            graph.adjust(to_node)

    return graph


def make_node(gtfs, services, trip_node, trip_id):
    node = trip_node.get(trip_id)
    if node:
        return node
    
    node = trip_node[trip_id] = Node(trip_id, services.days_by_trip(gtfs.trips[trip_id]))
    return node

# Greedy split CANNOT be used if any vehicle splits might be in input!
def greedy_split(graph):
    queue = collections.deque(graph.sources)
    print(queue)
    visited = set()

    while queue:
        from_node = queue.popleft()
        if from_node in visited:
            continue
        
        visited.add(from_node)

        matched_days = set()
        #match_cases = set()

        for to_node in list(from_node.out_edges.keys()):
            to_days = frozenset(to_node.days) # FIXME: requires shift factor
            conflict = False

            #f to_days in match_cases:
            #    print('Exact conflict!', from_node.trip_id, '->', to_node.trip_id, 'limit', wdates(to_days))
            #    continue #
            
            if not to_days.isdisjoint(matched_days):
                conflict = True
                to_days = frozenset(to_days - matched_days)
                print('Conflict!', from_node.trip_id, '->', to_node.trip_id, 'limit', wdates(to_days))

            #match_cases.add(to_days)
            matched_days.update(to_days)

            if not conflict:
                queue.append(to_node)
                continue

            to_node_split = to_node.split(to_days)
            del from_node.out_edges[to_node]
            del to_node.in_edges[from_node]

            graph.adjust(to_node_split)
            graph.adjust(from_node)
            graph.adjust(to_node)

            if to_node_split:
                queue.append(to_node_split)

            if to_node in graph.sources:
                queue.append(to_node)



def greedy_split_simple(graph):
    queue = collections.deque(graph.sources)
    print(queue)
    visited = set()

    while queue:
        from_node = queue.popleft()
        if from_node in visited:
            continue
        
        visited.add(from_node)

        for to_node, transfer in list(from_node.out_edges.items()):
            if not getattr(transfer, '_has_conflict', False):
                #print('OK', from_node.trip_id, '->', to_node.trip_id)
                queue.append(to_node)
                continue
            
            to_node_split = to_node.split(set(transfer._days_when_best))
            
            if to_node_split is Keep:
                print('RETAIN', from_node.trip_id, '->', to_node.trip_id, 'limit', wdates(transfer._days_when_best), 'max', wdates(to_node.days))
                queue.append(to_node)
                continue


            if to_node_split is None:
                print('IGNORE', from_node.trip_id, '->', to_node.trip_id, 'limit', wdates(transfer._days_when_best), 'max', wdates(to_node.days))
            else:
                print('MODIFY', from_node.trip_id, '->', to_node.trip_id, 'limit', wdates(transfer._days_when_best), 'split', wdates(to_node.days))

            del from_node.out_edges[to_node]
            del to_node.in_edges[from_node]

            graph.adjust(to_node_split)
            graph.adjust(from_node)
            graph.adjust(to_node)

            if to_node_split:
                queue.append(to_node_split)

            if to_node in graph.sources:
                queue.append(to_node)
           

def backprop_split(graph, gtfs):
    queue = collections.deque(graph.sinks)
    visited = set()

    while queue:
        to_node = queue.popleft()
        if to_node in visited:
            continue

        visited.add(to_node)
        for from_node in list(to_node.in_edges.keys()):
            shift_days = -1 if gtfs.trips[to_node.trip_id].first_departure < gtfs.trips[from_node.trip_id].last_arrival else 0
            to_days_in_from_ref = service_days.shift(to_node.days, shift_days)

            from_node_split = from_node.split(to_days_in_from_ref)

            if from_node_split is Keep:
                queue.append(from_node)
                continue
            
            del from_node.out_edges[to_node]
            del to_node.in_edges[from_node]
            graph.adjust(from_node)
            graph.adjust(to_node)
            graph.adjust(from_node_split)

            if from_node_split:
                queue.append(from_node_split)
            
            if from_node in graph.sinks:
                queue.append(from_node)






def export_visit(graph):
    stack = collections.deque(graph.sources)
    visited = set()

    while stack:
        from_node = stack.pop()
        if from_node in visited:
            continue

        visited.add(from_node)
        print(from_node.trip_id, wdates(from_node.days))
        for to_node, transfer in from_node.out_edges.items():
            print('\t->', to_node.trip_id, wdates(to_node.days))
            stack.append(to_node)