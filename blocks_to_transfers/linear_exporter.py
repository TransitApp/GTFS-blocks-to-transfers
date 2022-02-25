import collections
from blocks_to_transfers import simplify_graph

class Step:
    def __init__(self, node, limit_days, parent=None) -> None:
        self.node = node
        self.limit_days = limit_days
        self.parent = parent

    def has_node(self, target_node):
        current_entry = self
        while current_entry:
            if current_entry.node is target_node:
                return True

            current_entry = current_entry.parent
        return False


def ppath(cell):
    path = []
    path.append(cell.node.trip_id)
    while cell.parent:
        cell = cell.parent
        path.insert(0, cell.node.trip_id)

    return path

def export_visit(graph):
    break_cycles(graph)
    return find_paths(graph)

def break_cycles(graph):
    stack = collections.deque(graph.sources)
    pred = {}

    while stack:
        from_node = stack.pop()

        for to_node, transfer in list(from_node.out_edges.items()):
            if not from_node.has_trip() or not to_node.has_trip():
                shift_days = 0
            else:
                shift_days = -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0

            match_days = from_node.days.intersection(to_node.days.shift(shift_days))

            if on_path(pred, from_node, to_node):
                print(f'Prohibited cycle {from_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(match_days)}]')
                graph.del_edge(from_node, to_node) 
                match_days_reshifted = match_days.shift(-shift_days)
                from_node.term_node.days = from_node.term_node.days.union(match_days_reshifted)
                to_node.start_node.days = to_node.start_node.days.union(match_days)
                graph.adjust(from_node)
                graph.adjust(to_node)
                graph.adjust(from_node.term_node)
                graph.adjust(to_node.start_node)
                print(f'\tResolved {from_node.trip_id} -> {from_node.term_node.trip_id} [{graph.services.pdates(from_node.term_node.days)}]')
                print(f'\tResolved {to_node.start_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(to_node.start_node.days)}]')
                continue

            pred[to_node] = from_node
            stack.append(to_node)

def on_path(pred, last, search_node):
    current = last
    while current:
        if current is search_node:
            return True

        current = pred.get(current)

    return False



def find_paths(graph):
    """
    LINEAR EXPORTER DOES NOT LIKE IT IF VEHCILES JOIN OR SPLIT
    DO NOT UPSET LINEAR EXPORTER
    """
    transformed_graph = simplify_graph.Graph(graph.gtfs, graph.services)
    stack = collections.deque(Step(node, node.days) for node in graph.sources)

    while stack:
        from_entry = stack.pop()
        from_node = from_entry.node

        for to_node in from_node.out_edges.keys():
            if not from_node.has_trip() or not to_node.has_trip():
                shift_days = 0
            else:
                shift_days = -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0

            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = from_entry.limit_days.intersection(to_days_in_from_ref)

            if not match_days:
                # from_node and to_node aren't in any way connected on match_days
                continue

            if not to_node.has_trip() or from_entry.has_node(to_node):
                # End of block:
                #   - discovered a Residual node, which indicates the end of a block for these days
                #   - we're revisiting a node along the path (a cycle)
                add_path_to_graph(transformed_graph, from_entry, match_days)
            else:
                # A new edge continuing the block
                # Put match_days back in to_node's frame of reference
                match_days = match_days.shift(-shift_days)
                stack.append(Step(to_node, match_days, from_entry))
                    
    return transformed_graph

def add_path_to_graph(t_graph, last_entry, days):
    prev_node = simplify_graph.Node(last_entry.node.trip, days)
    t_graph.nodes.append(prev_node)
    t_graph.adjust(prev_node)

    current_entry = last_entry

    while current_entry.parent:
        parent = current_entry.parent

        if not parent.node.has_trip():
            break

        shifted_days = t_graph.services.days_in_from_frame(parent.node.trip, last_entry.node.trip, days)
        parent_node = simplify_graph.Node(parent.node.trip, shifted_days, out_edges={prev_node: parent.node.out_edges[current_entry.node]})
        t_graph.nodes.append(parent_node)
        t_graph.adjust(parent_node)

        prev_node = parent_node
        current_entry = parent
