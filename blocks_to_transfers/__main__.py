import argparse
import os
import json
import sys
import gtfs_loader
from . import config, classify_transfers, logs, runtime_config, processing


def main():
    cmd = argparse.ArgumentParser(
        description=
        'Predicts trip-to-trip transfers from block_ids in GTFS feeds')
    cmd.add_argument('feed', help='Path to a directory containing a GTFS feed')
    cmd.add_argument('out_dir', help='Directory to contain the modified feed')
    cmd.add_argument('-L',
                     '--linear',
                     action='store_true',
                     help='Apply linear simplification')
    cmd.add_argument(
        '--remove-existing-files',
        action='store_true',
        help='Remove all files in the output directory before exporting')
    cmd.add_argument(
        '--itineraries',
        action='store_true',
        help='Load and export Transit itinerary_cells.txt format instead of stop_times.txt.')
    cmd.add_argument(
        '-c',
        '--config',
        default='{}',
        help='Set config overrides in JSON (see config.py for options)')
    args = cmd.parse_args()

    if os.environ.get('VSCODE_DEBUG'):
        import debugpy
        print('Waiting for VSCode to attach')
        debugpy.listen(5678)
        debugpy.wait_for_client()

    runtime_config.apply(json.loads(args.config))

    try:
        processing.process(args.feed,
                args.out_dir,
                use_simplify_linear=args.linear,
                remove_existing_files=args.remove_existing_files,
                itineraries=args.itineraries)
    except (gtfs_loader.ParseError, classify_transfers.InvalidRuleError) as exc:
        # Skip backtrace for common issues which indicate data or config issues
        print(f'Error: {type(exc).__name__}: {exc}')
        sys.exit(1)

    if logs.Warn.any_warnings:
        sys.exit(2)


if __name__ == '__main__':
    main()
