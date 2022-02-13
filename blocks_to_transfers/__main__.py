import argparse
from collections import namedtuple
import os
from blocks_to_transfers import cut

from blocks_to_transfers.service_days import ServiceDays
from . import block_converter, editor
def process(in_dir, out_dir):
    gtfs = editor.load(in_dir)

    # Will be needed later to process existing trip-to-trip transfers
    services = ServiceDays(gtfs)

    converted_transfers, conflicts = block_converter.convert_blocks(gtfs, services)
    block_converter.add_transfers(gtfs, converted_transfers)
    cut.convert(gtfs, services, conflicts)

    #expand_dag.expand(data, trip_transfers)

    editor.patch(gtfs, gtfs_in_dir=in_dir, gtfs_out_dir=out_dir)
    print('Done.')


def main():
    cmd = argparse.ArgumentParser(description='Predicts trip-to-trip transfers from block_ids in GTFS feeds')
    cmd.add_argument('feed', help='Path to a GTFS feed')
    cmd.add_argument('out_dir', help='Directory to contain the modified feed')
    args = cmd.parse_args()

    if os.environ.get('VSCODE_DEBUG'):
        import debugpy
        print('Waiting for VSCode to attach')
        debugpy.listen(5678)
        debugpy.wait_for_client()  


    process(args.feed, args.out_dir)


if __name__ == '__main__':
    main()
