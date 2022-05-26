import functools
import enum
from datetime import datetime
from typing import Any


class GTFSTime(int):
    # GTFS allows times exceeding 23:59:59 as it is simpler to describe night
    # services that way in many cases. A trip could theoretically be shifted
    # forward an arbitrary number of days using this notation, but we block it
    # as it just creates confusion.
    MAX_HOUR_REPRESENTATION = 36

    def __new__(cls, time_str):
        if isinstance(time_str, int):
            return super().__new__(cls, time_str)

        if time_str == '':
            return super().__new__(cls, -1)

        h, m, s = time_str.split(':')

        if int(h) > GTFSTime.MAX_HOUR_REPRESENTATION:
            raise ValueError(
                f'Refusing to consider a service day longer than {GTFSTime.MAX_HOUR_REPRESENTATION} hours'
            )

        return super().__new__(cls, 3600 * int(h) + 60 * int(m) + int(s))

    def __str__(self):
        if self == -1:
            return ''

        hours, rem = divmod(self, 3600)
        mins, secs = divmod(rem, 60)
        return '%02d:%02d:%02d' % (hours, mins, secs)

    def __add__(self, other):
        return GTFSTime(super().__add__(other))

    def __sub__(self, other):
        return GTFSTime(super().__sub__(other))


class GTFSDate(datetime):

    def __new__(cls, *args, **kwargs):
        if len(args) != 1 or kwargs:
            return super().__new__(cls, *args, **kwargs)

        iso_str = args[0]
        if isinstance(iso_str, datetime):
            return super().__new__(cls,
                                   year=iso_str.year,
                                   month=iso_str.month,
                                   day=iso_str.day)

        if not iso_str:
            raise ValueError('Invalid date: empty')
        try:
            return cls.strptime(iso_str, '%Y-%m-%d')
        except ValueError:
            return cls.strptime(iso_str, '%Y%m%d')

    def __repr__(self):
        return self.strftime('%Y%m%d')

    def __str__(self):
        return repr(self)


class EntityDict(dict):

    def __init__(self, fields, values=None):
        super().__init__(values if values else [])
        self._resolved_fields = fields


class Entity:

    def __init__(self, **kwargs):
        self._gtfs = None
        default_init = {
            k: v
            for k, v in self.__class__.__dict__.items()
            if Entity._is_field(k, v)
        }
        self.__dict__.update(default_init)
        self.__dict__.update(kwargs)

    @staticmethod
    def _is_field(k, v):
        if callable(v) or isinstance(v, functools.cached_property):
            return False

        return not k.startswith('_')

    def __getitem__(self, item):
        return self.__dict__[item]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def __repr__(self):
        filtered_dict = {
            k: v for k, v in self.__dict__.items() if k not in {'_gtfs'}
        }
        return f'{self.__class__.__name__} {repr(filtered_dict)}'

    def clone(self, **overrides):
        merged = {
            k: v for k, v in self.__dict__.items() if Entity._is_field(k, v)
        }
        merged.update(overrides)
        return self.__class__(**merged)


@functools.singledispatch
def serialize(value: Any):
    return str(value)


@serialize.register
def _(value: enum.IntEnum):
    return str(int(value))


@serialize.register
def _(value: bool):
    return str(int(value))


@serialize.register
def _(value: None):
    return ''
