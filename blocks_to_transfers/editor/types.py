from datetime import datetime


class GTFSTime(int):
    def __new__(cls, time_str):
        if isinstance(time_str, int):
            return super().__new__(cls, time_str)

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

    def __sub__(self, other):
        return GTFSTime(super().__sub__(other))


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

    def __repr__(self):
        return self.strftime('%Y-%m-%d')

    def __str__(self):
        return repr(self)


class Entity:
    def __init__(self, **kwargs):
        default_init = {k: v for k, v in self.__class__.__dict__.items() if Entity._is_field(k, v)}
        self.__dict__.update(default_init)
        self.__dict__.update(kwargs)

    @staticmethod
    def _is_field(k, v):
        if callable(v):
            return False

        if k.startswith('_'):
            return False

        return k not in {'SCHEMA', 'data'}

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
        return f'{self.__class__.__name__} {repr(self.__dict__)}'

    def duplicate(self):
        return self.__class__(**self.__dict__)