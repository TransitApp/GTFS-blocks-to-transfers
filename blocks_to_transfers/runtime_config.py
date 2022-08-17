import json
from . import config


def apply(config_override_str):
    """
    Applies JSON configuration options passed at runtime
    """
    config_override = json.loads(config_override_str, 
            object_hook=GetDict)

    for section, options in config_override.items():
        if section == 'SpecialContinuations':
            # This section is a list
            config.__dict__[section] = options
        else:
            # Other sections are dicts
            for k, v in options.items():
                setattr(config.__dict__[section], k, v)

    for stop in config.InSeatTransfers.banned_stops:
        config.SpecialContinuations.append(GetDict(
            match=[GetDict(through=GetDict(stop=stop))],
            op='modify',
            transfer_type=5))


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

