import collections
import enum
from blocks_to_transfers import simplify_graph

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
            #print(f'{from_node.trip_id} {state[from_node]}')
            stack.pop()
            continue

        # Unvisited node has been entered
        state[from_node] = Visited.ENTER
        #print(f'{from_node.trip_id} {state[from_node]}')

        for to_node in list(from_node.out_edges.keys()):
            shift_days = get_shift(from_node, to_node)
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
    DO NOT UPSET LINEAR EXPORTER
    """

    transformed_graph = simplify_graph.Graph(graph.gtfs, graph.services)
    stack = collections.deque(Frame(source) for source in graph.sources)
    
    ####
    for node in graph.nodes:
        if node.vehicle_split or node.vehicle_join:
            stack.append(Frame(node))
    ####

    while stack:
        from_node = stack.pop()
        print(from_node.trip_id)
        for to_node in from_node.out_edges.keys():
            shift_days = get_shift(from_node, to_node)
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

            if to_node.vehicle_join or to_node.vehicle_split:
                # Acts like it were a sink node and ends the block
                add_path_to_graph(transformed_graph, last_frame=to_frame, days=match_days)
                continue

            stack.append(to_frame)
                    
    return transformed_graph

def add_path_to_graph(t_graph, last_frame, days):
    protected_nodes = {}
    current_frame = last_frame
    split_node = get_path_node(t_graph, protected_nodes, current_frame, days)

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
        parent_split_node = get_path_node(t_graph, protected_nodes, parent_frame, parent_days)
        parent_split_node.out_edges[split_node] = transfer
        split_node.in_edges[parent_split_node] = transfer
        split_node = parent_split_node
        current_frame = parent_frame


def get_path_node(t_graph, protected_nodes, frame, requested_days):
    if frame.node.vehicle_split or frame.node.vehicle_join:
        protected_node = protected_nodes.get(frame.node)
        if protected_node:
            print(f'Protected node {frame.trip_id} [{t_graph.services.bdates(frame.node.days)}] cannot be split')
            return protected_node

        protected_node = protected_nodes[frame.node] = simplify_graph.Node(frame.node.trip, frame.node.days)
        t_graph.add_node(protected_node)

        print(f'Protected node {frame.trip_id} [{t_graph.services.bdates(frame.node.days)}] cannot be split')
        return protected_node
    else:
        return t_graph.add(frame.trip, requested_days)



def get_shift(from_node, to_node):
    if from_node.has_trip() and to_node.has_trip():
        return -1 if to_node.trip.first_departure < from_node.trip.last_arrival else 0

    return 0

