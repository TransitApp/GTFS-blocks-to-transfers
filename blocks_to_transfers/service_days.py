from datetime import timedelta

from blocks_to_transfers.editor.schema import CalendarDate, ExceptionType
from blocks_to_transfers.editor.types import GTFSDate

def shift(day_set, num_days):
    if num_days == 0:
        return set(day_set)
    
    return {day + timedelta(days=num_days) for day in day_set}

class ServiceDays:
    def __init__(self, gtfs) -> None:
        print('Calculating days by service')
        self.gtfs = gtfs
        self.synth_service_counter = 0  # Number of services we needed to add to the feed
        self.days_by_service = ServiceDays.get_days_by_service(gtfs)
        self.service_by_days = ServiceDays.get_reverse_index(self.days_by_service)

    @staticmethod
    def get_days_by_service(gtfs):
        all_service_ids = gtfs.calendar.keys() | gtfs.calendar_dates.keys()
        days_by_service = {}
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for service_id in all_service_ids:
            service_days = days_by_service[service_id] = set()
            calendar = gtfs.calendar.get(service_id)
            if calendar:
                num_days = (calendar.end_date - calendar.start_date).days + 1
                current_day = calendar.start_date
                for _ in range(num_days):
                    weekday_name = weekdays[current_day.weekday()]

                    if calendar[weekday_name]:
                        service_days.add(current_day)

                    current_day += timedelta(days=1)

            for date in gtfs.calendar_dates.get(service_id, []):
                if date.exception_type == ExceptionType.ADD:
                    if date.date in service_days:
                        print(f'Warning: calendar_dates.txt adds {date.date} to {service_id} even though it already runs on this date')
                    service_days.add(date.date)
                else:
                    if date.date not in service_days:
                        print(f'Warning: calendar_dates.txt removes {date.date} from {service_id} even though it already is not running on this date')
                    service_days.discard(date.date)
        return days_by_service

    @staticmethod
    def get_reverse_index(days_by_service):
        return {frozenset(days): service_id for service_id, days in days_by_service.items()}

    def days_by_trip(self, trip, extra_shift=0):
        return shift(self.days_by_service[trip.service_id], trip.shift_days + extra_shift)

    def get_or_assign(self, days):
        """
        Given a set of days of operation, obtain the existing service_id in the feed, or create a synthetic 
        object to represent it (using calendar_dates.txt.)
        """
        days = frozenset(days)
        service_id = self.service_by_days.get(days)
        if service_id:
            return service_id
        
        service_id = f'b2t:service_{self.synth_service_counter}'
        self.synth_service_counter += 1
        self.service_by_days[days] = service_id
        self.gtfs.calendar_dates[service_id] = [CalendarDate(
            service_id=service_id,
            date=GTFSDate(day),
            exception_type=ExceptionType.ADD
        ) for day in days]

        return service_id

# For debugging

def pdates(dates):
    sdates = sorted(date.strftime('%m%d') for date in dates)
    tdates =  ', '.join(sdates[:14])
    if len(dates) > 14:
        tdates += ' ...'
    return tdates


def wdates(dates):
    sdates = sorted(date for date in dates)
    sdates = ['UMTWRFS'[int(date.strftime('%w'))] for date in sdates]
    tdates =  ''.join(sdates[:14])
    return tdates
