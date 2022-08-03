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
