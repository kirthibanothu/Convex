import math
import numpy as np

from convex.strategy_utils.utils import simple_midpoint


class RealizedVolatility:
    def __init__(self, window_size=1000, compute_interval=100):
        self._historical = []

        self._window_size = window_size
        self._compute_interval = compute_interval

        self._counter = 0
        self._value = 0

    @property
    def value(self):
        return self._value

    def _add(self, book):
        self._historical.append(math.log(simple_midpoint(book)))

    def on_market_data(self, book):
        self._add(book)

        self._counter += 1
        if self._counter > self._compute_interval:
            self._counter = 0

            returns = [0]
            prev = self._historical[0]
            for historical in self._historical[1:]:
                returns.append(prev - historical)

            self._value = np.std(np.asarray(returns))
