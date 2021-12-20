import argparse
import ctypes
import math
import timeit

from blocks_to_transfers.shape_similarity import LatLon, hausdorff
from . import editor, augment


def main():
    gtfs = editor.load('/Users/np/GTFSs/BCTWK_734/211_cleaned')
    gtfs = augment.augment(gtfs)

    shape_lats = {shape_id: [LatLon(pt.shape_pt_lat, pt.shape_pt_lon) for pt in pts] for shape_id, pts in gtfs.shapes.items()}


    """
    for a_id, a_pt in cleaned_shapes.items():
        for b_id, b_pt in cleaned_shapes.items():
            print(a_id, b_id, hausdorff(a_pt, b_pt))
    """

    haus_cache = {}
    for block, trips in gtfs.trips_by_block.items():
        for i_trip, trip in enumerate(trips):
            for trip2 in trips[i_trip+1:]:
                if not trip.data.shape_id or not trip2.data.shape_id:
                    continue

                key = (trip.data.shape_id, trip2.data.shape_id)
                rkey = (trip2.data.shape_id, trip.data.shape_id)
                if key not in haus_cache and rkey not in haus_cache:
                    haus_cache[key] = hausdorff(shape_lats[trip.data.shape_id], shape_lats[trip2.data.shape_id])
                    print('eval', key, haus_cache[key])


    #editor.patch(gtfs, gtfs_in_dir='/Users/np/GTFSs/BCTWK_734/211_cleaned', gtfs_out_dir='mimi')
    x = 5


if __name__ == '__main__':
    main()
