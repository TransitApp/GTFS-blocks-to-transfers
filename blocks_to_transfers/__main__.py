import argparse
from . import editor, augment, convert, invariant_transfers


def process(in_dir, out_dir):
    gtfs = editor.load(in_dir)
    data = augment.augment(gtfs)
    trip_transfers = convert.convert_blocks(data)
    convert.add_transfers(gtfs, trip_transfers)
    invariant_transfers.make_invariant(data)

    editor.patch(gtfs, gtfs_in_dir=in_dir, gtfs_out_dir=out_dir)
    print('Done.')


def main():
    cmd = argparse.ArgumentParser(description='Predicts trip-to-trip transfers from block_ids in GTFS feeds')
    cmd.add_argument('feed', help='Path to a GTFS feed')
    cmd.add_argument('out_dir', help='Directory to contain the modified feed')
    args = cmd.parse_args()
    process(args.feed, args.out_dir)


if __name__ == '__main__':
    main()
