import collections
import itertools


class Subscriber:
    def __init__(self, gateway, instrument, on_update, update_cache_size=2):
        self._gateway = gateway
        self._gateway.register(instrument, self._on_update)
        self._instrument = instrument
        self._update_cb = on_update

        # Build initial update cache
        updates_iter = itertools.repeat(None, update_cache_size)
        self._update_cache = collections.deque(updates_iter,
                                               maxlen=update_cache_size)

    def __del__(self):
        self._gateway.unregister(self._instrument, self._on_update)

    @property
    def instrument(self):
        return self._instrument

    def _on_update(self, update):
        self._update_cache.append(update)
        self._update_cb(update)

    @property
    def update_cache(self):
        return self._update_cache

    @property
    def latest_update(self):
        return self._update_cache[-1]

    @property
    def last_update(self):
        return self._update_cache[-2]
