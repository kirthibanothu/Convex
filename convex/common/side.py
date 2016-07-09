from enum import Enum


class Side(Enum):
    BID = BUY = 'b'
    ASK = SELL = 's'

    @property
    def opposite(self):
        return Side.ASK if self == Side.BID else Side.BID
