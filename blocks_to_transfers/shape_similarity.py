"""
Implements similarity metrics based on trip shapes, used by convert to predict whether or not a continuation represents
and in-seat transfer.
"""
from . import config
from math import *


def trip_shapes_similar(similarity_results, shape_a, shape_b):
    if shape_a is shape_b:
        return True

    cache_key = tuple(sorted((id(shape_a), id(shape_b))))
    cache_value = similarity_results.get(cache_key)

    if cache_value is not None:
        return cache_value
    else:
        return similarity_results.setdefault(
            cache_key, compute_shapes_similar(shape_a, shape_b))


def compute_shapes_similar(shape_a, shape_b):
    return hausdorff_percentile(
        shape_a,
        shape_b,
        threshold=config.InSeatTransfers.similarity_percentile
    ) < config.InSeatTransfers.similarity_distance


def hausdorff_percentile(shape_a, shape_b, threshold):
    distances = distance_point_to_nearest_segment(shape_points=shape_a,
                                                  shape_segments=shape_b)
    distances.extend(
        distance_point_to_nearest_segment(shape_points=shape_b,
                                          shape_segments=shape_a))
    return percentile(distances, threshold)


def percentile(values, threshold):
    # Percentile interpolation is based on: https://www.itl.nist.gov/div898/handbook/prc/section2/prc262.htm
    values.sort()
    float_index = threshold * (len(values) + 1)
    index, interpolation_factor = int(float_index // 1), float_index % 1

    if index == 0:
        return values[0]

    if index >= len(values):
        return values[-1]

    return values[index - 1] + interpolation_factor * (values[index] -
                                                       values[index - 1])


def distance_point_to_nearest_segment(shape_points, shape_segments):
    """
    For each point in the first shape, return the closest distance from that point to any point on the second shape.
    """
    distances = []
    for pt in shape_points:
        d_nearest_segment = inf
        for i_seg in range(len(shape_segments) - 1):
            d_point_segment = pt.distance_to_segment(shape_segments[i_seg],
                                                     shape_segments[i_seg + 1])
            if d_point_segment < d_nearest_segment:
                d_nearest_segment = d_point_segment

        distances.append(d_nearest_segment)

    return distances


class LatLon:
    # Sources:
    # http://www.movable-type.co.uk/scripts/gis-faq-5.1.html
    # http://www.movable-type.co.uk/scripts/latlong.html
    EARTH_RADIUS_M = 6_371_009.0
    __slots__ = ('lat', 'lon')

    def __init__(self, lat, lon, unit=degrees):
        self.lat = radians(lat) if unit == degrees else lat
        self.lon = radians(lon) if unit == degrees else lon

    def geojson(self):
        return f'[{degrees(self.lon)}, {degrees(self.lat)}]'

    def __repr__(self):
        return repr((degrees(self.lat), degrees(self.lon)))

    def angular_distance_to(self, other):
        d_lat = other.lat - self.lat
        d_lon = other.lon - self.lon
        a = sin(
            d_lat / 2)**2 + cos(self.lat) * cos(other.lat) * sin(d_lon / 2)**2
        return 2 * asin(sqrt(a))

    def distance_to(self, other):
        return LatLon.EARTH_RADIUS_M * self.angular_distance_to(other)

    def bearing_to(self, other):
        y = sin(other.lon - self.lon) * cos(other.lat)
        x = cos(self.lat) * sin(other.lat) - sin(self.lat) * cos(
            other.lat) * cos(other.lon - self.lon)
        return atan2(y, x)

    def add_bearing_and_angular_distance(self, bearing, dist):
        lat = asin(
            sin(self.lat) * cos(dist) +
            cos(self.lat) * sin(dist) * cos(bearing))
        lon = self.lon \
              + atan2(sin(bearing)*sin(dist)*cos(self.lat), cos(dist) - sin(self.lat)*sin(lat))

        return LatLon(lat, lon, unit=radians)

    def distance_to_segment(x, l1, l2):
        """
                     x
                     |
                     |
        l1 ---------lx------------ l2
        """

        d_l1_x, t_l1_x = l1.angular_distance_to(x), l1.bearing_to(x)
        d_l1_l2, t_l1_l2 = l1.angular_distance_to(l2), l1.bearing_to(l2)
        d_l2_x = l2.angular_distance_to(x)

        d_cross = asin(sin(d_l1_x) * sin(t_l1_x - t_l1_l2))
        d_along = acos(cos(d_l1_x) / cos(d_cross))

        lx = l1.add_bearing_and_angular_distance(t_l1_l2, d_along)
        d_lx_x = lx.angular_distance_to(x)

        if d_along < d_l1_l2 and d_lx_x < d_l1_x and d_lx_x < d_l2_x:
            # closest point is somewhere along l1-l2 as in the above figure
            return LatLon.EARTH_RADIUS_M * d_lx_x
        else:
            # closest point is l1, l2 depending on which end is nearer to x
            return LatLon.EARTH_RADIUS_M * min(d_l1_x, d_l2_x)

    def __eq__(self, other):
        return self.lat == other.lat and self.lon == other.lon

    def __hash__(self):
        return hash((self.lat, self.lon))
