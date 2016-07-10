import asyncio
import collections

import logbook

from .update import Update

log = logbook.Logger('MD')


class Subscriber:
    def __init__(self, instrument, gateway, update_cache_size=2):
        self._instrument = instrument
        self._update_event = asyncio.Event(loop=gateway.loop)
        gateway.register(instrument, self._on_update)
        assert(update_cache_size >= 1)
        self._updates = collections.deque(maxlen=update_cache_size)
        self._update_sequence = 0
        self._cached_trades = []

    @property
    def cached_updates(self):
        return reversed(self._updates)

    @property
    def update_cache_size(self):
        return self._updates.maxlen

    @property
    def instrument(self):
        return self._instrument

    def has_update(self):
        return self._update_event.is_set()

    async def fetch(self):
        if self.has_update():
            return self._fetch_pending_update()
        await self._update_event.wait()
        return self._fetch_pending_update()

    def fetch_nowait(self):
        if self.has_update():
            return self._fetch_pending_update()
        return None

    def _fetch_pending_update(self):
        assert(self.has_update())
        self._update_event.clear()
        latest_update = self._updates[-1]
        full_update = Update.replace_trades(latest_update,
                                            trades=self._cached_trades.copy())
        self._cached_trades.clear()
        return full_update

    def _check_ordering(self, update):
        if not self._updates:
            return True
        prev_book_id = self._updates[-1].book_id
        if prev_book_id <= update.book_id:
            return True
        log.warn('Invalid book ID ordering, prev={}, last={}',
                 prev_book_id, update.book_id)
        return False

    async def _on_update(self, update):
        if not self._check_ordering(update):
            return
        self._cached_trades.extend(update.trades)
        self._update_sequence += 1
        self._updates.append(update)
        self._update_event.set()
