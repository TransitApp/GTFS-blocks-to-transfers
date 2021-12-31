"""
When a single from_trip_id has transfers to multiple to_trip_ids, it may represent either of the following situations:
(1) A vehicle splits at the end of its journey (e.g. train cars are decoupled and proceed to different destinations)
(2) A single vehicle will serve various trips depending on the day of service (e.g. a continuation trip uses a different
    route on Friday evenings.)

Additionally, even when there is a single to_trip_id, the continuation trip might not operate on all of the days that
from_trip_id operates on (e.g. additional trips on weekdays only.)

This module makes trip-to-trip transfers 'invariant of service', that is to say that for every day of service of
from_trip_id, all of the to_trip_ids are also operating. This requires duplicating from_trip_id for each variant case,
and generating a synthetic service describing those days on which it occurs.
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

    added_transfers = specialized_transfers(data)

    # Insert the 'specialized forms' of any transfers we discover
    for transfer in added_transfers:
        data.gtfs.transfers.setdefault(transfer.from_trip_id, {})[transfer.to_trip_id] = transfer

    # TBD: replace all references to the cluster roots with references to each of their members


def specialized_transfers(data):
    added_transfers = []
    for from_trip_id, transfers in data.gtfs.transfers.items():
        # Other types of transfers (e.g. stop-to-stop)
        if not from_trip_id:
            continue

        days_to_match = set(data.days_by_service[data.gtfs.trips[from_trip_id].service_id])
        from_trip = data.gtfs.trips[from_trip_id]
        shift_days = 1 if from_trip.shifted_to_next_day else 0

        for to_trip_id, transfer in transfers.items():
            # We have to do the fucking 24h correction again
            to_trip = data.gtfs.trips[to_trip_id]
            print(from_trip.last_arrival, to_trip.first_departure)
            wraparound = 1 if to_trip.first_departure < from_trip.last_arrival else 0

            days_when_running = convert.get_shifted_days_of_service(data.days_by_service, to_trip,
                                                                    shift_days + wraparound)

            days_when_running.intersection_update(days_to_match)
            if not days_when_running:
                print(f'Warning! Transfer between trips that never run on same day {from_trip_id} -> {to_trip_id}')

            days_to_match.difference_update(days_when_running)

            if days_to_match:
                specialized_trip_id = specialize(data, from_trip_id, days_when_running)
                # Insert a transfer referring to the specialized trip
                specialized_transfer = transfer.duplicate()
                specialized_transfer.from_trip_id = specialized_trip_id
                added_transfers.append(specialized_transfer)
                print('Variable continuation [fork type]', specialized_trip_id, from_trip_id, to_trip_id)

        if days_to_match:
            specialized_trip_id = specialize(data, from_trip_id, days_to_match)
            print('Variable continuation [terminal type]', specialized_trip_id, from_trip_id)

    return added_transfers


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


