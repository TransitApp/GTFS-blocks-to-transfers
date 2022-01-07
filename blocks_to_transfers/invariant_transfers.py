"""
If a from_trip_id has multiple trip-to-trip transfers, this might represent a train splitting up to continue on to
multiple destinations, but it could also represent a varying continuation depending on the day of service, e.g.:

    from_trip_id,to_trip_id,transfer_type
    trip_bus_15,trip_bus_50_via_howe,5 # Friday evenings only
    trip_bus_15,trip_bus_50_via_granville,5 # All other times

Even when there is only one outgoing trip-to-trip transfer, the to_trip_id might only run on certain days (e.g. an added
run on weekdays).

This module 'specializes' the from_trip_id to ensure that each trip's continuations are always applicable on all days
of operation.
"""
from . import config, convert
from .editor import duplicate
from .editor.schema import *
from .editor.types import GTFSDate


def make_invariant(data):
    if not config.TripToTripTransfers.invariant_transfers:
        return

    print('Making trip-to-trip transfers invariant of service')
    data.service_id_for_days = {frozenset(days): service_id for service_id, days in data.days_by_service.items()}
    data.num_split_services = 0
    data.clusters = {}

    # Narrow down from_trip_ids to intersect with each of their to_trip_ids
    data.gtfs.transfers = specialized_transfers(data)

    # Find incoming transfers to any modified trips and expand them for each specialized trip created
    #data.gtfs.transfers = expand_incoming_transfers(data, with_specialized_transfers)


def specialized_transfers(data):
    with_specialized_transfers = {}
    for from_trip_id, transfers_out in data.gtfs.transfers.items():
        # Other types of transfers (e.g. stop-to-stop)
        if not from_trip_id:
            continue

        from_days = data.days_by_service[data.gtfs.trips[from_trip_id].service_id]

        variants = set()

        unmatched_from_days = set(from_days)
        from_trip = data.gtfs.trips[from_trip_id]
        shift_days = 1 if from_trip.shifted_to_next_day else 0

        for to_trip_id, transfer in transfers_out.items():
            to_trip = data.gtfs.trips[to_trip_id]
            wraparound = 1 if to_trip.first_departure < from_trip.last_arrival else 0

            to_days = convert.get_shifted_days_of_service(data.days_by_service, to_trip,
                                                                    shift_days + wraparound)

            transfer.continuation_days = frozenset(from_days.intersection(to_days))
            unmatched_from_days.difference_update(to_days)
            variants.add(transfer.continuation_days)

        if not unmatched_from_days and len(variants) <= 1:
            # Pass-through
            with_specialized_transfers[from_trip_id] = transfers_out.copy()
            continue

        for variant_days in variants:
            specialized_trip_id = specialize(data, from_trip_id, variant_days)

            for to_trip_id, transfer in transfers_out.items():
                if not variant_days.intersection(transfer.continuation_days):
                    continue

                specialized_transfer = transfer.duplicate()
                specialized_transfer.from_trip_id = specialized_trip_id
                with_specialized_transfers.setdefault(specialized_trip_id, {})[to_trip_id] = specialized_transfer
                print('Variable continuation [fork type]', specialized_trip_id, from_trip_id, to_trip_id)

        if unmatched_from_days:
            specialized_trip_id = specialize(data, from_trip_id, unmatched_from_days)
            print('Variable continuation [terminal type]', specialized_trip_id, from_trip_id)

    return with_specialized_transfers

"""
    new_transfers = with_specialized_transfers.setdefault(from_trip_id, {})
    for to_trip_id, transfer in transfers_out.items():
        new_transfers[to_trip_id] = transfer

    continue

    specialized_trip_id = specialize(data, from_trip_id, to_days)

    # Insert a transfer referring to the specialized trip
    specialized_transfer = transfer.duplicate()
    specialized_transfer.from_trip_id = specialized_trip_id
    with_specialized_transfers.setdefault(specialized_trip_id, {})[to_trip_id] = specialized_transfer
    print('Variable continuation [fork type]', specialized_trip_id, from_trip_id, to_trip_id)


if unmatched_from_days:
    specialized_trip_id = specialize(data, from_trip_id, unmatched_from_days)
    print('Variable continuation [terminal type]', specialized_trip_id, from_trip_id)
"""


def expand_incoming_transfers(data, transfers):
    expanded_transfers = {}
    for from_trip_id, transfers_out in transfers.items():
        for to_trip_id, transfer in transfers_out.items():
            specialized_trip_ids = data.clusters.get(to_trip_id, {}).values()
            if not specialized_trip_ids:
                expanded_transfers.setdefault(from_trip_id, {})[to_trip_id] = transfer

            for specialized_trip_id in specialized_trip_ids:
                in_transfer = transfer.duplicate()
                in_transfer.to_trip_id = specialized_trip_id

                expanded_transfers.setdefault(from_trip_id, {})[specialized_trip_id] = in_transfer

    return expanded_transfers


def specialize(data, trip_id, days):
    service_id = ensure_service(data, days)
    return specialized_trip_for_service(data, trip_id, service_id)


def specialized_trip_for_service(data, trip_id, service_id):
    cluster = data.clusters.setdefault(trip_id, {})

    existing_value = cluster.get(service_id)
    if existing_value:
        return existing_value

    specialized_trip_id = f'{trip_id}_b2t:if_{service_id}'
    cluster[service_id] = specialized_trip_id
    duplicate(data.gtfs.trips, trip_id, specialized_trip_id)
    data.gtfs.trips[specialized_trip_id].service_id = service_id
    duplicate(data.gtfs.stop_times, trip_id, specialized_trip_id)
    return specialized_trip_id


def ensure_service(data, days):
    days = frozenset(days)
    service_id = data.service_id_for_days.get(days)
    if service_id:
        return service_id

    return create_service_from_days(data, days)


def create_service_from_days(data, days):
    service_id = f'b2t:service_{data.num_split_services}'
    data.num_split_services += 1
    data.service_id_for_days[days] = service_id
    data.gtfs.calendar_dates[service_id] = [CalendarDate(
        service_id=service_id,
        date=GTFSDate(day),
        exception_type=ExceptionType.ADD
    ) for day in days]

    return service_id


