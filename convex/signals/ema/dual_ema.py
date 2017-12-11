from .ema_tracker import EMATracker
from convex.strategy_utils.utils import simple_midpoint, is_valid_book


StateColors = {"BUY": "#16a085", "SELL": "#f39c12"}


class DualEMA:
    def __init__(self, slow, fast, on_init_cb=None, on_signal_cb=None):
        self._on_init_cb = on_init_cb
        self._on_signal_cb = on_signal_cb

        self.reset(slow, fast)

    def reset(self, slow, fast):
        self._slow_window = slow
        self._fast_window = fast

        self._slow_value = 0.0
        self._fast_value = 0.0

        self._init_sum = 0.0
        self._init_processed = 0

        self._action = None

        self._is_initialized = False

    @property
    def slow_value(self):
        return self._slow_value

    @property
    def fast_value(self):
        return self._fast_value

    @property
    def is_initialized(self):
        return self._is_initialized

    @property
    def action_color(self):
        if self._action is not None:
            return StateColors[self._action]

    @property
    def action(self):
        return self._action

    @property
    def mkt_price(self):
        return self._mkt_price

    async def _on_init_complete(self, update):
        self._slow = EMATracker(self._slow_window, self._slow_value)
        self._fast = EMATracker(self._fast_window, self._fast_value)

        self._mkt_price = simple_midpoint(update['book'])

        slow = self._slow.on_price(self._mkt_price)
        fast = self._fast.on_price(self._mkt_price)

        self._action = 'BUY' if (fast > slow) else 'SELL'

        self._is_initialized = True

        if self._on_init_cb:
            await self._on_init_cb()

    async def initialize(self, update):
        assert self._init_processed != -1

        if is_valid_book(update['book']):
            self._init_processed += 1

            self._init_sum += simple_midpoint(update['book'])
            if self._init_processed == self._fast_window:
                self._fast_value = self._init_sum / self._fast_window
            if self._init_processed == self._slow_window:
                self._slow_value = self._init_sum / self._slow_window

                self._init_processed = -1
                await self._on_init_complete(update)

    async def on_market_data(self, update):
        assert self._init_processed is -1

        if not is_valid_book(update['book']):
            return

        self._mkt_price = simple_midpoint(update['book'])

        self._slow_value = self._slow.on_price(self._mkt_price)
        self._fast_value = self._fast.on_price(self._mkt_price)

        if self._action == 'BUY':
            if self._fast_value < self._slow_value:
                self._action = 'SELL'
                if self._on_signal_cb:
                    await self._on_signal_cb(self._action, update)
        else:
            if self._fast_value > self._slow_value:
                self._action = 'BUY'
                if self._on_signal_cb:
                    await self._on_signal_cb(self._action, update)

    def get_prices(self):
        return (self._slow.value, self._fast.value, self._fastest.value)
