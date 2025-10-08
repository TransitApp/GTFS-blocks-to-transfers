import gtfs_loader
from gtfs_loader.schema import TransferType, PickupType

def set_pickup_drop_off(gtfs, itineraries=False):
    for from_trip_id, transfers in gtfs.transfers.items():
        for transfer in transfers:
            transfer_type = transfer.transfer_type
            to_trip_id = transfer.to_trip_id

            if not (from_trip_id and to_trip_id):
                continue

            if transfer_type == TransferType.IN_SEAT or transfer_type == TransferType.IN_SEAT_TRIP_PLANNING_ONLY:
                if itineraries:
                    from_trip = gtfs.trips[from_trip_id]
                    to_trip = gtfs.trips[to_trip_id]
                    itin_idx_from = from_trip.itinerary_index + '_last_pickup_allowed'
                    itin_idx_to = 'first_dropoff_allowed_' + to_trip.itinerary_index
                    if itin_idx_from not in gtfs.itinerary_cells:
                        gtfs_loader.clone(gtfs.itinerary_cells, from_trip.itinerary_index, itin_idx_from)
                        gtfs.itinerary_cells[itin_idx_from][-1].pickup_type = PickupType.REGULARLY_SCHEDULED
                    if itin_idx_to not in gtfs.itinerary_cells:
                        gtfs_loader.clone(gtfs.itinerary_cells, to_trip.itinerary_index, itin_idx_to)
                        gtfs.itinerary_cells[itin_idx_to][0].drop_off_type = PickupType.REGULARLY_SCHEDULED
                    from_trip.itinerary_index = itin_idx_from
                    to_trip.itinerary_index = itin_idx_to
                else:
                    gtfs.stop_times[from_trip_id][-1].pickup_type = PickupType.REGULARLY_SCHEDULED
                    gtfs.stop_times[to_trip_id][0].drop_off_type = PickupType.REGULARLY_SCHEDULED                

    if itineraries:
        used_itin_indices = set()
        for trip in gtfs.trips.values():
            used_itin_indices.add(trip.itinerary_index)
        unused_itin_indices = set(gtfs.itinerary_cells.keys()) - used_itin_indices
        for itin_idx in unused_itin_indices:
            del gtfs.itinerary_cells[itin_idx]
