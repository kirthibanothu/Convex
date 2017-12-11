class EMATracker:
    def __init__(self, periods, value):
        self._value = value
        self._multiplier = (2/(periods + 1))

    @property
    def value(self):
        return self._value

    def _compute_ema(self, price, prev):
        return (price - prev)*self._multiplier + prev

    def _compute_dema(self, price, ema):
        return (2*ema)-(self._compute_ema(price, ema))

    def on_price(self, price):
        ema = self._compute_ema(price, self._value)
        self._value = self._compute_dema(price, ema)
        return self._value
