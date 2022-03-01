import collections
import enum
from blocks_to_transfers import simplify_graph
from blocks_to_transfers.service_days import ServiceDays

def simplify(graph):
    break_cycles(graph)
    return find_paths(graph)


def break_cycles(graph):
    """
    Break cyclic blocks by removing back edges that cause the trips to 
    repeat, as we cannot store cycles in our existing format.

    We begin the search only at source nodes, because we know that there must 
    be a first day for every trip, on which there were no preceding trips in 
    the cycle. For example, the earliest day a cycle could begin is the first 
    day of the feed.
    """
    class Visited(enum.Enum):
        ENTER = 0
        EXIT = 1

    stack = collections.deque(graph.sources)
    state = {}

    while stack:
        from_node = stack[-1]

        assert state.get(from_node) != Visited.EXIT
        
        if state.get(from_node) == Visited.ENTER:
            # All children of this node are now visited
            state[from_node] = Visited.EXIT
            stack.pop()
            continue

        # Unvisited node has been entered
        state[from_node] = Visited.ENTER

        for to_node in list(from_node.out_edges.keys()):
            shift_days = ServiceDays.get_shift(from_node.trip, to_node.trip)
            match_days = from_node.days.intersection(to_node.days.shift(shift_days))

            if to_node not in state:
                # Unvisited node
                stack.append(to_node) 
                continue

            if state[to_node] == Visited.EXIT:
                # Alternative path to a visited node
                continue 

            # Cycle: edge is removed, days along edge reassigned to sink node 
            # of from_node and source node of to_node
            print(f'Cycle {to_node.trip_id} -> ... -> {from_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(match_days)}]')
            graph.del_edge(from_node, to_node) 
            
            match_days_reshifted = match_days.shift(-shift_days)
            from_node.sink_node.days = from_node.sink_node.days.union(match_days_reshifted)
            graph.sinks.add(from_node.sink_node)

            to_node.source_node.days = to_node.source_node.days.union(match_days)
            graph.sources.add(to_node.source_node)
            print(f'\tResolved {from_node.trip_id} -> {from_node.sink_node.trip_id} [{graph.services.pdates(from_node.sink_node.days)}]')
            print(f'\tResolved {to_node.source_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(to_node.source_node.days)}]')


class Frame:
    def __init__(self, node, parent=None, days=None):
        self.node = node
        self.parent = parent
        self.days = days if days is not None else self.node.days

    def __getattr__(self, key):
        return getattr(self.node, key)


def find_paths(graph):
    """
    Enumerates all paths in the continuation graph, keeping track of the 
    intersection of all service days (limiting constraint). A new node is
    created for each step in the path, meaning that every trip has 0/1 in-edges
    and 0/1 out-edges, excepting 'composite nodes' which are not modified.
    """
    transformed_graph = simplify_graph.Graph(graph.gtfs, graph.services)
    stack = collections.deque(Frame(source) for source in graph.sources)
    
    for node in graph.nodes:
        if node.composite:
            stack.append(Frame(node))

    while stack:
        from_node = stack.pop()
        for to_node in from_node.out_edges.keys():
            shift_days = ServiceDays.get_shift(from_node.trip, to_node.trip)
            to_days_in_from_ref = to_node.days.shift(shift_days)
            match_days = from_node.days.intersection(to_days_in_from_ref)

            if not match_days:
                # from_node and to_node aren't in any way connected on match_days
                continue

            if not to_node.has_trip():
                # End of the block (sink node encountered)
                add_path_to_graph(transformed_graph, last_frame=from_node, days=match_days) 
                continue

            # A new edge continuing the block
            # Put match_days back in to_node's frame of reference
            match_days = match_days.shift(-shift_days)

            # FIXME: What happens if the very first trip of the year requires shifting back?
            to_frame = Frame(to_node, parent=from_node, days=match_days)

            if to_node.composite:
                # Acts like it were a sink node and ends the block
                print(f'Composite node {to_node.trip_id} will not be split along {from_node.trip_id} -> {to_node.trip_id}')
                add_path_to_graph(transformed_graph, last_frame=to_frame, days=match_days)
                continue

            stack.append(to_frame)
                    
    return transformed_graph


def add_path_to_graph(t_graph, last_frame, days):
    composite_nodes = {}
    current_frame = last_frame
    split_node = get_path_node(t_graph, composite_nodes, current_frame, days)

    while True:
        parent_frame = current_frame.parent

        if not parent_frame or not parent_frame.has_trip():
            # Reached the end of the path
            # Even though export will work anyway, injecting a source node can improve the readability of transfers.txt
            split_node.source_node.days = days
            t_graph.sources.add(split_node.source_node)
            break


        parent_days = t_graph.services.days_in_from_frame(parent_frame.trip, last_frame.trip, days)
        transfer = parent_frame.out_edges[current_frame.node]
        parent_split_node = get_path_node(t_graph, composite_nodes, parent_frame, parent_days)
        t_graph.add_edge(parent_split_node, split_node, transfer)
        split_node = parent_split_node
        current_frame = parent_frame


def get_path_node(t_graph, composite_nodes, frame, requested_days):
    if not frame.composite:
        return t_graph.add(frame.trip, requested_days)

    composite_node = composite_nodes.get(frame.node)
    if composite_node:
        return composite_node

    composite_node = composite_nodes[frame.node] = simplify_graph.Node(frame.node.trip, frame.node.days)
    t_graph.add_node(composite_node)

    return composite_node
