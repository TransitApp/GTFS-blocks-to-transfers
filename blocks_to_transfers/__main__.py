import argparse
import ctypes
import math
import timeit

from blocks_to_transfers.shape_similarity import trip_shapes_similar, compute_shapes_similar
from . import editor, augment


def main():
    gtfs = editor.load('/Users/np/GTFSs/TSL_32/131_preprocessed')
    gtfs = augment.augment(gtfs)

    shape_similarity_cache = {}
    for block, trips in gtfs.trips_by_block.items():
        for i_trip, trip in enumerate(trips):
            for cont_trip in trips[i_trip+1:]:
                wait_time = cont_trip.first_departure - trip.last_arrival
                if wait_time < 0:
                    print('Block is corrupted!')
                    break

                if wait_time > 600:
                    #print('wait too long')
                    break

                similarity = compute_shapes_similar(trip.shape, cont_trip.shape)
                if trip.shape_id != cont_trip.shape_id:
                    print(trip.route_id, cont_trip.route_id, similarity)
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





    #editor.patch(gtfs, gtfs_in_dir='/Users/np/GTFSs/BCTWK_734/211_cleaned', gtfs_out_dir='mimi')
    x = 5


if __name__ == '__main__':
    main()
