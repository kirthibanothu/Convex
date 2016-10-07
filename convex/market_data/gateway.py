import asyncio
from collections import defaultdict

import logbook

from . import Book, Status, Update

log = logbook.Logger('MD')


class Gateway:
    class InstrumentHandler:
        def __init__(self):
            self._book = None
            self._sequence = -1
            self._trades = []
            self._status = Status.UNKNOWN

        def set_status(self, status):
            self._status = status

        def make_book(self):
            if self._book:
                return self._book.make_book(self._sequence)
            else:
                return Book(-1, [], [])

        def set_book(self, sequence, book):
            self._book = book
            self._sequence = sequence

        def add_trade(self, trade):
            self._trades.append(trade)

        def take_update(self):
            trades = self._trades.copy()
            self._trades.clear()
            return self.make_book(), trades, self._status

    def __init__(self, loop=None):
        self._loop = loop if loop else asyncio.get_event_loop()
        self._callbacks = defaultdict(set)  # instrument -> {callbacks}
        self._handlers = defaultdict(Gateway.InstrumentHandler)
        self._updated = set()
        self._timestamp = 0

    @property
    def loop(self):
        """Event loop."""
        return self._loop

    async def launch(self):
        """Start running gateway."""
        raise NotImplementedError()

    def subscribe(self, instrument):
        """Have gateway subscribe to data for instrument."""
        raise NotImplementedError()

    def register(self, instrument, on_update):
        """Register update callback for instrument.

        ``on_update`` must be a coroutine accepting a ``market_data.Update`` as
        the only paramemter.
        """
        cbs = self._callbacks[instrument]
        if not cbs:
            self.subscribe(instrument)
        cbs.add(on_update)

    def set_timestamp(self, timestamp):
        """Update gateway timestamp."""
        self._timestamp = timestamp

    def add_trade(self, instrument, trade):
        """Add trade."""
        self._updated.add(instrument)
        self._handlers[instrument].add_trade(trade)

    def set_book(self, instrument, sequence, book):
        """Update stored book."""
        self._updated.add(instrument)
        self._handlers[instrument].set_book(sequence, book)

    def set_status(self, instrument, status):
        """Update stored market data status"""
        log.info('[{}] Setting status {}', instrument, status)
        self._updated.add(instrument)
        self._handlers[instrument].set_status(status)

    def publish(self):
        """PUblish updates"""
        for instrument, handler in self._handlers.items():
            book, trades, status = handler.take_update()
            update = Update(instrument=instrument,
                            book=book,
                            trades=trades,
                            status=status,
                            timestamp=self._timestamp)
            self._publish_update(update)

    def _publish_update(self, update):
        """Publish update to subscribers."""
        cbs = [cb(update) for cb in self._callbacks[update.instrument]]
        asyncio.ensure_future(*cbs, loop=self._loop)
