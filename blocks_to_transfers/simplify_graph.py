import enum
from . import service_days


class Graph:

    def __init__(self, gtfs, services):
        self.gtfs = gtfs
        self.services = services
        self.sources = set()
        self.sinks = set()
        self.nodes = []

    def add(self, *args, **kwargs):
        return self.add_node(Node(*args, **kwargs))

    def add_node(self, node):
        self.nodes.append(node)
        return node

    def make_primary_node(self, primary_nodes, trip_id):
        node = primary_nodes.get(trip_id)
        if node:
            return node

        trip = self.gtfs.trips[trip_id]
        node = primary_nodes[trip_id] = self.add(
            trip, self.services.days_by_trip(trip))
        return node

    def make_primary_edge(self, primary_nodes, transfer):
        from_node = self.make_primary_node(primary_nodes, transfer.from_trip_id)
        to_node = self.make_primary_node(primary_nodes, transfer.to_trip_id)
        self.add_edge(from_node, to_node, transfer)

    def add_edge(self, from_node, to_node, transfer):
        from_node.out_edges[to_node] = to_node.in_edges[from_node] = transfer

    def del_edge(self, from_node, to_node):
        del from_node.out_edges[to_node]
        del to_node.in_edges[from_node]

    def split(self, from_node, to_node, days):
        """
        Take target_node (currently always to_node) and make a new node 
        representing a subset of its days of operation. The new node has all 
        the connections the previous node did, except that it replaces the 
        connection between from_node and to_node.
        """

        target_node = to_node
        new_days = days.intersection(target_node.days)

        if len(new_days) == 0:
            self.del_edge(from_node, to_node)
            return None

        target_node.days = target_node.days.difference(new_days)
        assert len(target_node.days) > 0

        node_split = Node(target_node.trip, new_days,
                          target_node.in_edges.copy(),
                          target_node.out_edges.copy())
        self.add_node(node_split)
        self.del_edge(from_node, to_node)
        return node_split


class BaseNode:

    def __init__(self, trip, days, in_edges, out_edges):
        self.days = days
        self.in_edges = in_edges
        self.out_edges = out_edges
        self.composite = False
        self.trip = trip

        for in_node, edge in self.in_edges.items():
            in_node.out_edges[self] = edge

        for out_node, edge in self.out_edges.items():
            out_node.in_edges[self] = edge

    def has_trip(self):
        return self.trip is not None

    @property
    def trip_id(self):
        return self.trip.trip_id if self.has_trip() else '<NIL>'


class Node(BaseNode):

    def __init__(self, trip, days, in_edges=None, out_edges=None):
        in_edges = in_edges or EdgeDict()
        out_edges = out_edges or EdgeDict()
        super().__init__(trip, days, in_edges, out_edges)

        self.source_node = BaseNode(None, service_days.DaySet(), EdgeDict(),
                                    EdgeDict({self: None}))
        self.sink_node = BaseNode(None, service_days.DaySet(), EdgeDict({self: None}), EdgeDict())


class EdgeType(enum.Enum):
    IN = 0
    OUT = 1


class EdgeDict(dict):
    def has_predefined_transfers(self):
        return any(transfer and not transfer.is_generated for transfer in self.values())

    def generated_by_rank(self):
        return sorted(self._filter_generated(), key=lambda kv: kv[1]._rank)
        
    def _filter_generated(self):
        for to_node, transfer in self.items():
            if not to_node.has_trip():
                continue

            if transfer.is_generated:
                yield (to_node, transfer)

    def copy(self):
        return EdgeDict(super().copy())

