class Instrument:
    __slots__ = '_symbol', '_venue_data'

    def __init__(self, symbol, venue_data=None):
        self._symbol = symbol
        self._venue_data = venue_data if venue_data else dict()

    @property
    def symbol(self):
        return self._symbol

    @property
    def venue_data(self):
        return self._venue_data
