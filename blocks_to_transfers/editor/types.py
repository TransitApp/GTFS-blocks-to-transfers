from datetime import datetime


class GTFSTime(int):
    def __new__(cls, time_str):
        if time_str == '':
            return super().__new__(cls, -1)

        h, m, s = time_str.split(':')

        return super().__new__(cls, 3600*int(h) + 60*int(m) + int(s))

    def __str__(self):
        if self == -1:
            return ''

        hours, rem = divmod(self, 3600)
        mins, secs = divmod(rem, 60)
        return '%02d:%02d:%02d' % (hours, mins, secs)


class GTFSDate(datetime):
    def __new__(cls, *args, **kwargs):
        if len(args) != 1 or kwargs:
            return super().__new__(cls, *args, **kwargs)

        iso_str = args[0]
        if not iso_str:
            raise ValueError('Invalid date: empty')
        try:
            return cls.strptime(iso_str, '%Y-%m-%d')
        except ValueError:
            return cls.strptime(iso_str, '%Y%m%d')

    def __str__(self):
        return self.strftime('%Y-%m-%d')


def as_bool(bool_str):
    return bool(int(bool_str))


def as_lat(float_str):
    lat = float(float_str)
    assert abs(lat) <= 90
    return lat


def as_lon(float_str):
    lon = float(float_str)
    assert abs(lon) <= 180
    return lon


def as_enum(enum_type, default=None):
    def convert(value):
        if value == '' and default is not None:
            return default
        else:
            return enum_type(int(value))

    return convert


class Entity(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

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


class ExportDict(dict):
    pass
