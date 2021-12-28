from blocks_to_transfers.editor import duplicate
from blocks_to_transfers.editor.schema import *


def insert_transfers(data, from_trip, to_trips):
    if not to_trips:
        return

    if len(to_trips) == 1:
        insert_transfer(data, from_trip, to_trips[0])
        return

    # There are 2+ continuations, depending on the day of service.
    # For each transfer:
    # (1) Duplicate the trip with a new ID. Duplicate all of its stop times
    # (2) Is there an existing service with the same days as this continuation? If so set the service ID
    # (3) Create a set of calendar_dates describing this new service
    # (4) Insert the transfer to the duplicate trip
    for to_trip in to_trips:
        cloned_trip_id = f'{from_trip.trip_id}-blocks2transfers#{data.num_duplicated_trips}'
        cloned_trip = duplicate(data.gtfs.trips, from_trip.trip_id, cloned_trip_id)
        data.gtfs.transfers[cloned_trip_id] = {}
        data.transfers_in[cloned_trip_id] = {}

        duplicate(data.gtfs.stop_times, from_trip.trip_id, cloned_trip_id)

        # Existing transfer from this trip, now also come from the cloned trip
        for to_trip_id, transfer in data.gtfs.transfers.get(from_trip.trip_id, {}).items():
            clone_transfer = transfer.duplicate()
            clone_transfer.from_trip_id = cloned_trip_id
            data.gtfs.transfers[cloned_trip_id][to_trip_id] = clone_transfer
            data.transfers_in.setdefault(to_trip_id, {})[cloned_trip_id] = clone_transfer

        # All incoming transfers to this trip also refer to the clone
        for from_trip_id, transfer in data.transfers_in.get(from_trip.trip_id, {}).items():
            # Create a new transfer object referring to the clone of the trip
            clone_transfer = transfer.duplicate()
            clone_transfer.to_trip_id = cloned_trip_id
            data.gtfs.transfers[from_trip_id][cloned_trip_id] = clone_transfer
            data.transfers_in.setdefault(cloned_trip_id, {})[from_trip_id] = clone_transfer

        data.num_duplicated_trips += 1

        service_id = data.service_by_days.get(to_trip.days_when_best)
        if not service_id:
            service_id = create_service_from_days(data, to_trip.days_when_best)

        cloned_trip.service_id = service_id
        insert_transfer(data, cloned_trip, to_trip)

    delete_trip(data, from_trip.trip_id)


def insert_transfer(data, from_trip, to_trip):
    if to_trip.transfer_type is TransferType.NOT_POSSIBLE:
        return

    new_transfer = Transfer(
        from_trip_id=from_trip.trip_id,
        to_trip_id=to_trip.trip.trip_id,
        transfer_type=to_trip.transfer_type
    )

    print('create', from_trip.trip_id, to_trip.trip.trip_id)
    data.gtfs.transfers.setdefault(from_trip.trip_id, {})[to_trip.trip.trip_id] = new_transfer
    data.transfers_in.setdefault(to_trip.trip.trip_id, {})[from_trip.trip_id] = new_transfer


def create_service_from_days(data, days):
    service_id = f'blocks2transfers#{data.num_split_services}'
    data.num_split_services += 1
    data.service_by_days[days] = service_id
    data.gtfs.calendar_dates[service_id] = [CalendarDate(
        service_id=service_id,
        date=GTFSDate(day),
        exception_type=ExceptionType.ADD
    ) for day in days]

    return service_id


def delete_trip(data, trip_id):
    del data.gtfs.trips[trip_id]
    del data.gtfs.stop_times[trip_id]
    if trip_id in data.gtfs.transfers:
        del data.gtfs.transfers[trip_id]

    if trip_id in data.transfers_in:
        for dest_trip in data.transfers_in[trip_id]:
            print('destroy', dest_trip, trip_id)
            del data.gtfs.transfers[dest_trip][trip_id]

        del data.transfers_in[trip_id]




