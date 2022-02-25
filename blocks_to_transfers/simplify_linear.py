import collections
from blocks_to_transfers import simplify_graph

def simplify(graph):
    break_cycles(graph)
    return find_paths(graph)


def break_cycles(graph):
    stack = collections.deque(graph.sources)
    previous_node = {}

    while stack:
        from_node = stack.pop()

        for to_node in list(from_node.out_edges.keys()):
            shift_days = get_shift(from_node, to_node)
            match_days = from_node.days.intersection(to_node.days.shift(shift_days))

            if on_path(previous_node, from_node, to_node):
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

            previous_node[to_node] = from_node
            stack.append(to_node)


def find_paths(graph):
    """
    LINEAR EXPORTER DOES NOT LIKE IT IF VEHCILES JOIN OR SPLIT
    DO NOT UPSET LINEAR EXPORTER
    """
    transformed_graph = simplify_graph.Graph(graph.gtfs, graph.services)
    stack = collections.deque(graph.sources)
    previous_node = {}
    limiting_days = {node: node.days for node in graph.sources}

    while stack:
        from_node = stack.pop()

        for to_node in from_node.out_edges.keys():
            shift_days = get_shift(from_node, to_node)
            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = limiting_days[from_node].intersection(to_days_in_from_ref)

            if not match_days:
                # from_node and to_node aren't in any way connected on match_days
                continue

            if not to_node.has_trip() or on_path(previous_node, from_node, to_node):
                # End of block:
                #   - discovered a Residual node, which indicates the end of a block for these days
                #   - we're revisiting a node along the path (a cycle)
                add_path_to_graph(transformed_graph, previous_node, from_node, match_days)
            else:
                # A new edge continuing the block
                # Put match_days back in to_node's frame of reference
                match_days = match_days.shift(-shift_days)
                previous_node[to_node] = from_node
                limiting_days[to_node] = match_days
                stack.append(to_node)
                    
    return transformed_graph


def add_path_to_graph(t_graph, previous_node, last_node, days):
    visited_node = last_node
    split_node = simplify_graph.Node(visited_node.trip, days)
    t_graph.nodes.append(split_node)
    t_graph.adjust(split_node)


    while True:
        visited_parent = previous_node[visited_node]

        if not visited_parent.has_trip():
            break

        shifted_days = t_graph.services.days_in_from_frame(visited_parent.trip, last_node.trip, days)
        split_parent = simplify_graph.Node(visited_parent.trip, shifted_days, out_edges={split_node: visited_parent.out_edges[visited_node]})
        t_graph.nodes.append(split_parent)
        t_graph.adjust(split_parent)

        split_node = split_parent
        visited_node = visited_parent


def get_shift(from_node, to_node):
    if from_node.has_trip() and to_node.has_trip():
        shift_days = -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0

    return 0


def on_path(previous_node, last, search_node):
    current = last
    while current:
        if current is search_node:
            return True

        current = previous_node.get(current)

    return False
