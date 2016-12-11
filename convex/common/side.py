from enum import Enum


_ASK_REPS = 'ask', 'sell', 'a'
_BID_REPS = 'bid', 'buy', 'b'


class Side(Enum):
    """Side enumeration.

    Representing bid, ask, buy, and sell.
    """
    BID = BUY = 'b'
    ASK = SELL = 's'

    @staticmethod
    def parse(s):
        """Parse string into Side.

        raises ``ValueError`` if cannot parse.
        """
        if s in _ASK_REPS:
            return Side.ASK
        if s in _BID_REPS:
            return Side.BID
        raise ValueError('Cannot convert {} to Side'.format(s))

    @property
    def opposite(self):
        """Opposite side."""
        return Side.ASK if self == Side.BID else Side.BID
