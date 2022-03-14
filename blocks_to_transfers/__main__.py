import argparse
import os
import shutil
from . import convert_blocks, editor, service_days, classify_transfers, simplify_graph, simplify_linear, simplify_export


def process(in_dir,
            out_dir,
            use_simplify_linear=False,
            remove_existing_files=False):
    gtfs = editor.load(in_dir)

    services = service_days.ServiceDays(gtfs)
    converted_transfers = convert_blocks.convert(gtfs, services)
    classify_transfers.classify(gtfs, converted_transfers)

    graph = simplify_graph.simplify(gtfs, services, converted_transfers)

    if use_simplify_linear:
        output_graph = simplify_linear.simplify(graph)
    else:
        output_graph = graph
    simplify_export.export_visit(output_graph)

    if remove_existing_files:
        shutil.rmtree(out_dir, ignore_errors=True)

    editor.patch(gtfs, gtfs_in_dir=in_dir, gtfs_out_dir=out_dir)
    print('Done.')


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
        help='Remove all files in the output directory before expoting')
    args = cmd.parse_args()

    if os.environ.get('VSCODE_DEBUG'):
        import debugpy
        print('Waiting for VSCode to attach')
        debugpy.listen(5678)
        debugpy.wait_for_client()

    process(args.feed,
            args.out_dir,
            use_simplify_linear=args.linear,
            remove_existing_files=args.remove_existing_files)


if __name__ == '__main__':
    main()
