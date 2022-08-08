from datetime import timedelta, datetime

from gtfs_loader.schema import CalendarDate, ExceptionType
from gtfs_loader.types import GTFSDate


class DaySet(int):

    def __new__(cls, num=0):
        return super().__new__(cls, num)

    def intersection(a, b):
        return DaySet(a & b)

    def union(a, b):
        return DaySet(a | b)

    def difference(a, b):
        return DaySet(a & ~b)

    def isdisjoint(a, b):
        return a & b == 0

    def issuperset(a, b):
        return a & b == b

    def isequal(a, b):
        return a == b

    def shift(day_set, num_days):
        if num_days >= 0:
            return DaySet(day_set << num_days)

        return DaySet(day_set >> abs(num_days))

    def __getitem__(self, day):
        return self & (1 << day) != 0

    def __len__(self):
        return self.bit_length()

    def __iter__(self):
        for i in range(len(self)):
            if self[i]:
                yield i


class ServiceDays:

    def __init__(self, gtfs) -> None:
        print('Calculating days by service')
        self.gtfs = gtfs
        self.synth_service_counter = 0  # Number of services we needed to add to the feed
        self.init_days_by_service(gtfs)
        self.service_by_days = ServiceDays.get_reverse_index(
            self.days_by_service)

    def init_days_by_service(self, gtfs):
        all_service_ids = gtfs.calendar.keys() | gtfs.calendar_dates.keys()
        days_by_service = {}
        weekdays = [
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
            'sunday'
        ]

        # 1. Find a plausible starting point for the feed
        start_day = datetime.max
        end_day = datetime.min
        for calendar in gtfs.calendar.values():
            start_day = min(start_day, calendar.start_date)
            end_day = max(end_day, calendar.end_date)

        for dates in gtfs.calendar_dates.values():
            for date in dates:
                if date.exception_type == ExceptionType.REMOVE:
                    continue
                start_day = min(start_day, date.date)
                end_day = max(end_day, date.date)

        num_days = (end_day - start_day).days + 1

        for service_id in all_service_ids:
            service_days = 0
            calendar = gtfs.calendar.get(service_id)

            if calendar:
                num_days = (calendar.end_date - calendar.start_date).days + 1
                current_day = calendar.start_date
                start_index = (current_day - start_day).days

                for i in range(num_days):
                    weekday_name = weekdays[current_day.weekday()]

                    if calendar[weekday_name]:
                        date_index = 1 << (start_index + i)
                        service_days |= date_index

                    current_day += timedelta(days=1)

            for date in gtfs.calendar_dates.get(service_id, []):
                date_index = 1 << (date.date - start_day).days
                if date.exception_type == ExceptionType.ADD:
                    service_days |= date_index
                else:
                    service_days &= ~(date_index)

            days_by_service[service_id] = DaySet(service_days)

        self.days_by_service = days_by_service
        self.epoch = start_day

    @staticmethod
    def get_reverse_index(days_by_service):
        return {
            days: service_id for service_id, days in days_by_service.items()
        }

    def days_by_trip(self, trip, extra_shift=0):
        return self.days_by_service[trip.service_id].shift(trip.shift_days +
                                                           extra_shift)

    @staticmethod
    def get_shift(from_trip, to_trip):
        if from_trip is None or to_trip is None:
            return 0

        return -1 if to_trip.first_departure < from_trip.last_arrival else 0

    def days_in_from_frame(self, from_trip, to_trip, days):
        return days.shift(ServiceDays.get_shift(from_trip, to_trip))

    def days_in_to_frame(self, from_trip, to_trip, days):
        return days.shift(-ServiceDays.get_shift(from_trip, to_trip))

    def get_or_assign(self, trip, days):
        """
        Given a set of days of operation, obtain the existing service_id in the feed, or create a synthetic 
        object to represent it (using calendar_dates.txt.)
        """

        # Restore original representation of trip's days if it started after midnight
        days = days.shift(-trip.shift_days)

        service_id = self.service_by_days.get(days)
        if service_id:
            return service_id

        service_id = f'b2t:service_{self.synth_service_counter}'
        self.synth_service_counter += 1
        self.service_by_days[days] = service_id

        self.gtfs.calendar_dates[service_id] = [
            CalendarDate(service_id=service_id,
                         date=GTFSDate(date),
                         exception_type=ExceptionType.ADD)
            for date in self.to_dates(days)
        ]

        return service_id

    def to_dates(self, day_set):
        for offset in day_set:
            yield self.epoch + timedelta(days=offset)

    def bdates(self, dates):
        return wdates(self.to_dates(dates))

    def pdates(self, dates):
        return pdates(list(self.to_dates(dates)))


def pdates(dates):
    sdates = sorted(date.strftime('%m-%d') for date in dates)
    tdates = ', '.join(sdates[:14])
    if len(dates) > 14:
        tdates += ' ...'
    return tdates


def wdates(dates):
    sdates = sorted(date for date in dates)
    sdates = ['UMTWRFS'[int(date.strftime('%w'))] for date in sdates]
    tdates = ''.join(sdates[:14])
    return tdates
