from .status import Status


class Update:
    __slots__ = '_instrument', '_book', '_trades', '_status'

    def __init__(self, instrument, book, trades=None, status=None):
        self._instrument = instrument
        self._book = book
        self._trades = trades if trades else []
        self._status = status if status else Status.UNKNOWN

    @property
    def instrument(self):
        return self._instrument

    @property
    def book(self):
        return self._book

    @property
    def is_ok(self):
        return self._status == Status.OK

    def trades_before(self, book_id):
        return filter(lambda t: t.book_id < book_id, self._trades)

    def trades_after(self, book_id):
        return filter(lambda t: t.book_id >= book_id, self._trades)

    @property
    def trades(self):
        return self._trades

    @property
    def status(self):
        return self._status

    def show(self, max_depth=5):
        book_id = self._book.book_id
        res = '{}: {}\n'.format(self._instrument, self._status)
        trades_before = self.trades_before(book_id)
        trades_after = self.trades_after(book_id)
        for trade in trades_before:
            res += '{}\n'.format(trade)
        res += self._book.show(max_depth)
        for trade in trades_after:
            res += '\n{}'.format(trade)
        return res
