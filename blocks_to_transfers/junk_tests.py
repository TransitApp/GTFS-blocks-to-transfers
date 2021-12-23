import statistics

from blocks_to_transfers.shape_similarity import percentile


def test_percentile():
    data = [95.1772,95.1567,95.1937,95.1959,95.1442,95.0610,95.1591,95.1195,95.1065,95.0925,95.1990,95.1682]
    print(sorted(data))
    print(statistics.median(data))
    print(percentile(data, .5))


"""
          if trip.shape_id != cont_trip.shape_id:
              similarity = trip_shapes_similar(gtfs, shape_similarity_cache, trip, cont_trip)
              c1 = trip.shape_id.split('-')[1]
              c2 = cont_trip.shape_id.split('-')[1]
              if not similarity and c1 == c2:
                  print(trip.shape_id, cont_trip.shape_id, similarity)
          break
              # Surprising differences
          """