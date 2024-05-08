import collections
import enum
from . import simplify_graph
from .service_days import ServiceDays
from .logs import Warn


def simplify(graph):
    print('Applying linear simplification')
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
            match_days = from_node.days.intersection(
                to_node.days.shift(shift_days))

            if to_node not in state:
                # Unvisited node
                stack.append(to_node)
                continue

            if state[to_node] == Visited.EXIT:
                # Alternative path to a visited node
                continue

            # Cycle: edge is removed, days along edge reassigned to sink node
            # of from_node and source node of to_node
            graph.del_edge(from_node, to_node)

            match_days_reshifted = match_days.shift(-shift_days)
            from_node.sink_node.days = from_node.sink_node.days.union(
                match_days_reshifted)
            graph.sinks.add(from_node.sink_node)

            to_node.source_node.days = to_node.source_node.days.union(
                match_days)
            graph.sources.add(to_node.source_node)

            Warn(f'''
                Cycle {to_node.trip_id} -> ... -> {from_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(match_days)}]
                Resolved {from_node.trip_id} -> {from_node.sink_node.trip_id} [{graph.services.pdates(from_node.sink_node.days)}]
                Resolved {to_node.source_node.trip_id} -> {to_node.trip_id} [{graph.services.pdates(to_node.source_node.days)}]
            ''').print()


class Transition:
    """
    Represents a transition between nodes representing two trips. A Transition
    is a step in a path of nodes. Each transition is applicable on the most 
    specific set of service days encountered along the path.
    """

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
    stack = collections.deque(Transition(source) for source in graph.sources)

    for node in graph.nodes:
        if node.composite:
            stack.append(Transition(node))

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
                add_path_to_graph(transformed_graph,
                                  last_transition=from_node,
                                  days=match_days)
                continue

            # A new edge continuing the block
            # Put match_days back in to_node's transition of reference
            match_days = match_days.shift(-shift_days)

            # FIXME: What happens if the very first trip of the year requires shifting back?
            to_transition = Transition(to_node,
                                       parent=from_node,
                                       days=match_days)

            if to_node.composite:
                # Acts like it were a sink node and ends the block
                Warn(
                    f'Composite node {to_node.trip_id} will not be split along {from_node.trip_id} -> {to_node.trip_id}'
                ).print()
                add_path_to_graph(transformed_graph,
                                  last_transition=to_transition,
                                  days=match_days)
                continue

            stack.append(to_transition)

    return transformed_graph


def add_path_to_graph(t_graph, last_transition, days):
    print('path through graph')
    composite_nodes = {}
    parent_days = days
    current_transition = last_transition
    split_node = get_path_node(t_graph, composite_nodes, current_transition,
                               days)

    while True:
        parent_transition = current_transition.parent

        if not parent_transition or not parent_transition.has_trip():
            # Reached the end of the path
            # Even though export will work anyway, injecting a source node can improve the readability of transfers.txt
            split_node.source_node.days = parent_days
            t_graph.sources.add(split_node.source_node)
            break

        parent_days = t_graph.services.days_in_from_frame(
            parent_transition.trip, current_transition.trip, parent_days)
        
    
        if (parent_transition.trip.trip_id == '38912020' and last_transition.trip.trip_id == '73180020'):
            print(parent_transition.trip.trip_id, last_transition.trip.trip_id)
            print(t_graph.services.bdates(days))
            print(t_graph.services.bdates(parent_days))
        if (parent_transition.trip.trip_id == '38912020' and last_transition.trip.trip_id == '19526070'):
            print(parent_transition.trip.trip_id, last_transition.trip.trip_id)
            print(t_graph.services.bdates(days))
            print(t_graph.services.bdates(parent_days))
        if (parent_transition.trip.trip_id == '35863070' and last_transition.trip.trip_id == '19526070'):
            print(parent_transition.trip.trip_id, last_transition.trip.trip_id)
            print(t_graph.services.bdates(days))
            print(t_graph.services.bdates(parent_days))
        if (parent_transition.trip.trip_id == 'trip_0'):
            print('Parent Transition', parent_transition.trip.trip_id, last_transition.trip.trip_id)
            print('Parent Transition Days', t_graph.services.bdates(days))
            print('Parent Transition Parent Days', t_graph.services.bdates(parent_days))
        transfer = parent_transition.out_edges[current_transition.node]
        parent_split_node = get_path_node(t_graph, composite_nodes,
                                          parent_transition, parent_days)
        t_graph.add_edge(parent_split_node, split_node, transfer)
        split_node = parent_split_node
        current_transition = parent_transition


def get_path_node(t_graph, composite_nodes, transition, requested_days):
    if not transition.composite:
        return t_graph.add(transition.trip, requested_days)

    composite_node = composite_nodes.get(transition.node)
    if composite_node:
        return composite_node

    composite_node = composite_nodes[transition.node] = simplify_graph.Node(
        transition.node.trip, transition.node.days)
    t_graph.add_node(composite_node)

    return composite_node
