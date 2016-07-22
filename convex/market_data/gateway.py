import asyncio
from collections import defaultdict


class Gateway:
    def __init__(self, loop=None):
        self._loop = loop if loop else asyncio.get_event_loop()
        self._callbacks = defaultdict(set)  # instrument -> {callbacks}

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

    def _publish_update(self, update):
        """Publish update to subscribers."""
        cbs = [cb(update) for cb in self._callbacks[update.instrument]]
        asyncio.ensure_future(*cbs, loop=self._loop)
