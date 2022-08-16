from typing import List, Optional
from dataclasses import dataclass
from enum import IntEnum
from gtfs_loader.schema import TransferType

class Operation(IntEnum):
    # Change the predicted transfer type for existing blocks
    MODIFY = 0

    # Create a new block and assign the transfer type to all its continuations
    CREATE_BLOCK = 1 

    # Delete the block. Transfer type must not be specified.
    # WARNING: This option should rarely be used: To prevent the display of continuations to users,
    # simply Modify the transfer type to 5 (vehcile continuation only)
    REMOVE = 2

@dataclass
class SpecificRule:
    match: List['MatchCriteria']
    op: Operation = Operation.MODIFY
    transfer_type: Optional[TransferType] = None


@dataclass
class MatchCriteria:
    all: Optional['AllSelector'] = None
    through: Optional['ThroughSelector'] = None
    from_trip: Optional['FromTripSelector'] = None
    to_trip: Optional['ToTripSelector'] = None


AllSelector = bool

@dataclass
class ThroughSelector:
    route: Optional[str] = None
    stop: Optional[str] = None


@dataclass
class FromTripSelector:
    route: Optional[str] = None
    last_stop: Optional[str] = None

    @property
    def stop(self):
        return self.last_stop

@dataclass
class ToTripSelector:
    route: Optional[str] = None
    first_stop: Optional[str] = None

    @property
    def stop(self):
        return self.first_stop

