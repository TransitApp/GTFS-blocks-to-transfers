import gtfs_loader
import shutil
from . import convert_blocks, service_days, classify_transfers, simplify_fix, simplify_linear, simplify_export, set_pickup_drop_off


def process(in_dir,
            out_dir,
            use_simplify_linear=False,
            remove_existing_files=False,
            sorted_io=False,
            ):
    gtfs = gtfs_loader.load(in_dir, sorted_read=sorted_io)

    services = service_days.ServiceDays(gtfs)
    converted_transfers = convert_blocks.convert(gtfs, services)
    classify_transfers.classify(gtfs, converted_transfers)

    graph = simplify_fix.simplify(gtfs, services, converted_transfers)

    if use_simplify_linear:
        output_graph = simplify_linear.simplify(graph)
    else:
        output_graph = graph
    simplify_export.export_visit(output_graph)

    set_pickup_drop_off.set_pickup_drop_off(gtfs)

    if remove_existing_files:
        shutil.rmtree(out_dir, ignore_errors=True)

    gtfs_loader.patch(gtfs, gtfs_in_dir=in_dir, gtfs_out_dir=out_dir, 
            sorted_output=sorted_io)

    print('Done.')
