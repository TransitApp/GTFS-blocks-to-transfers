import json
from . import config


def apply(config_override):
    """
    Applies configuration options passed at runtime
    """
    for section, options in config_override.items():
        if section == 'SpecialContinuations':
            # This section is a list
            config.__dict__[section] = options
        else:
            # Other sections are dicts
            for k, v in options.items():
                setattr(config.__dict__[section], k, v)

    for stop in config.InSeatTransfers.banned_stops:
        config.SpecialContinuations.append({
            'match': [{'through': {'stop': stop}}],
            'op': 'modify',
            'transfer_type': 5})

    config.SpecialContinuations = GetDict.convert_rec(config.SpecialContinuations)

class GetDict(dict):
    """
    Works like a read-only defaultdict, returning None on missing values.
    """

    def __getitem__(self, k):
        return self.get(k)

    def __getattr__(self, k):
        return self[k]

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        del self[k]

    @staticmethod
    def convert_rec(data):
        if isinstance(data, dict):
            return GetDict((k, GetDict.convert_rec(v)) for k,v in data.items())
        elif isinstance(data, list):
            return [GetDict.convert_rec(v) for v in data]
        else:
            return data
