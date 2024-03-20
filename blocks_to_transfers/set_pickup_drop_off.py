from gtfs_loader.schema import TransferType, PickupType

def set_pickup_drop_off(gtfs):
    for from_trip_id, transfers in gtfs.transfers.items():
        for transfer in transfers:
            transfer_type = transfer.transfer_type
            to_trip_id = transfer.to_trip_id

            if not (from_trip_id and to_trip_id):
                continue

            if transfer_type in TransferType and transfer_type != TransferType.IN_SEAT:
                continue
            
            gtfs.stop_times[from_trip_id][-1].pickup_type = PickupType.REGULARLY_SCHEDULED
            gtfs.stop_times[to_trip_id][0].drop_off_type = PickupType.REGULARLY_SCHEDULED
