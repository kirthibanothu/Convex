class Update:
    __slots__ = '_instrument', '_book', '_trades', '_status'

    def __init__(self, instrument, book, trades=None, status=None):
        self._instrument = instrument
        self._book = book
        self._trades = trades
        self._status = status

    @property
    def instrument(self):
        return self._instrument

    @property
    def book(self):
        return self._book

    @property
    def trades(self):
        return self._trades if self._trades else []

    @property
    def status(self):
        return self._status
