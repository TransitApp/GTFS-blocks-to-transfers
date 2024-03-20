from gtfs_loader.schema import TransferType, PickupType

def set_pickup_drop_off(gtfs):
    from_trip_ids_to_set = set()
    to_trip_ids_to_set = set()
    for from_trip_id, transfers in gtfs.transfers.items():
        for transfer in transfers:
            transfer_type = transfer.transfer_type
            to_trip_id = transfer.to_trip_id

            if not (from_trip_id and to_trip_id):
                continue
            if transfer_type in TransferType and transfer_type != TransferType.IN_SEAT:
                continue
            
            from_trip_ids_to_set.add(from_trip_id)
            to_trip_ids_to_set.add(to_trip_id)
            
    for trip_id in from_trip_ids_to_set:
        gtfs.stop_times.get(trip_id)[-1].pickup_type = PickupType.REGULARLY_SCHEDULED
    for trip_id in to_trip_ids_to_set:
        gtfs.stop_times.get(trip_id)[0].drop_off_type = PickupType.REGULARLY_SCHEDULED
