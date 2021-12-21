import statistics

from blocks_to_transfers.shape_similarity import percentile


def test_percentile():
    data = [95.1772,95.1567,95.1937,95.1959,95.1442,95.0610,95.1591,95.1195,95.1065,95.0925,95.1990,95.1682]
    print(sorted(data))
    print(statistics.median(data))
    print(percentile(data, .5))

test_percentile()