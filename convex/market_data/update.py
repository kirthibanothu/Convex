import datetime as dt

from .status import Status


class Update:
    __slots__ = '_instrument', '_book', '_trades', '_status', '_timestamp'

    @staticmethod
    def replace_trades(update, trades):
        return Update(
                instrument=update.instrument,
                book=update.book,
                trades=trades,
                status=update.status,
                timestamp=update.timestamp)

    def __init__(self,
                 instrument,
                 book,
                 trades=None,
                 status=None,
                 timestamp=None):
        self._instrument = instrument
        self._book = book
        self._trades = trades if trades else []
        self._status = status if status else Status.UNKNOWN
        self._timestamp = timestamp if timestamp else dt.datetime.now()

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def instrument(self):
        return self._instrument

    @property
    def book(self):
        return self._book

    @property
    def book_id(self):
        return self._book.book_id

    @property
    def is_ok(self):
        return self._status == Status.OK

    def trades_before_book(self):
        return filter(lambda t: t.book_id <= self.book_id, self._trades)

    def trades_after_book(self):
        return filter(lambda t: t.book_id > self.book_id, self._trades)

    @property
    def trades(self):
        return self._trades

    @property
    def status(self):
        return self._status

    def show(self, max_depth=5):
        res = '{}: {} - {}\n'.format(
                self._instrument,
                self._status,
                self._timestamp)
        trades_before = self.trades_before_book()
        trades_after = self.trades_after_book()
        res += self._book.show(max_depth)
        res += 'Before book\n'
        for trade in trades_before:
            res += '{}\n'.format(trade)
        res += 'After book:\n'
        for trade in trades_after:
            res += '{}\n'.format(trade)

        return res
