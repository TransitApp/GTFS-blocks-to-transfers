import collections
from blocks_to_transfers import simplify_graph

class PathEntry:
    def __init__(self, node, limit_days, parent=None, via_transfer=None) -> None:
        self.node = node
        self.limit_days = limit_days
        self.parent = parent
        self.via_transfer = via_transfer

    def has_node(self, target_node):
        current_entry = self
        while current_entry:
            if current_entry.node is target_node:
                return True

            current_entry = current_entry.parent
        return False


def ppath(cell):
    path = []
    path.append('Residual' if cell.node.trip is simplify_graph.ResidualTrip else cell.node.trip_id)
    while cell.parent:
        cell = cell.parent
        path.insert(0, 'Residual' if cell.node.trip is simplify_graph.ResidualTrip else cell.node.trip_id)

    return path



def export_visit(graph):
    """
    LINEAR EXPORTER DOES NOT LIKE CYCLES
    LINEAR EXPORTER DOES NOT LIKE IT IF VEHCILES JOIN OR SPLIT
    DO NOT UPSET LINEAR EXPORTER
    """
    transformed_graph = simplify_graph.Graph(graph.gtfs, graph.services)
    stack = collections.deque(PathEntry(node, node.days) for node in graph.sources)

    while stack:
        from_entry = stack.pop()
        from_node = from_entry.node

        for to_node, transfer in from_node.out_edges.items():
            if from_node.trip is simplify_graph.ResidualTrip or to_node.trip is simplify_graph.ResidualTrip:
                shift_days = 0
            else:
                shift_days = -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0

            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = from_entry.limit_days.intersection(to_days_in_from_ref)
            # undo the shift on match days
            match_days = match_days.shift(-shift_days)

            if match_days:
                if to_node.trip is simplify_graph.ResidualTrip:
                    # ResidualTrip has no outgoing edges - it marks the end of a block along this path
                    add_path_to_graph(transformed_graph, from_entry, match_days)
                elif from_entry.has_node(to_node):
                    # Would form a cycle - export the last edge to close the path; do not continue
                    closing_entry = PathEntry(to_node, match_days, from_entry, transfer)
                    add_path_to_graph(transformed_graph, closing_entry, match_days)
                else:
                    # A new edge continuing the block
                    stack.append(PathEntry(to_node, match_days, from_entry, transfer))
                    

    return transformed_graph

def add_path_to_graph(t_graph, last_entry, days):
    prev_node = simplify_graph.Node(last_entry.node.trip, days)
    t_graph.nodes.append(prev_node)
    t_graph.adjust(prev_node)

    current_entry = last_entry

    while current_entry.parent:
        parent = current_entry.parent

        if parent.node.trip is simplify_graph.ResidualTrip:
            break

        shifted_days = t_graph.services.days_in_from_frame(parent.node.trip, last_entry.node.trip, days)
        parent_node = simplify_graph.Node(parent.node.trip, shifted_days, out_edges={prev_node: current_entry.via_transfer})
        t_graph.nodes.append(parent_node)
        t_graph.adjust(parent_node)

        prev_node = parent_node
        current_entry = parent
