from decimal import Decimal
from .logger import log

from .utils import to_json
from convex.common import Side

StateColors = {"active": "#27ae60", "halted": "#c0392b"}

UNINITIALIZED = -1


def round_to(val):
    return round(val, 8)


class BasicPnLManager():
    # need to hook this up to the session event handlers
    # Computes PnL from the on_fill calls
    def __init__(self, *,
                 get_balance_cb,
                 broadcast_cb,
                 crypto_coins,
                 cash_value,
                 instrument):

        # Callbacks - Coroutines, need to be awaited
        self._get_balance_cb = get_balance_cb
        self._broadcast_cb = broadcast_cb

        # Theoretical values if we just held
        self._initial_coins = UNINITIALIZED
        self._initial_cash = UNINITIALIZED
        self._initial_account_value = UNINITIALIZED

        # State
        self._refresh_int = 15

        self._total_fees = Decimal(0.0)
        self._num_traded = 0
        self._traded_qty = Decimal(0.0)
        self._num_updates = 1

        self._crypto_coins = crypto_coins
        self._cash_value = cash_value

        self._instrument = instrument

        self._is_strategy_running = True

        self._pnl = {}

        # Uninitialized
        self._strategy_val = 0.0
        self._last_price = UNINITIALIZED

    @property
    def total_fees(self):
        return self._total_fees

    @property
    def num_trades(self):
        return self._num_traded

    @property
    def crypto_coins(self):
        assert self._crypto_coins >= Decimal(0.0)
        return self._crypto_coins

    def _initialize(self, price):
        self._initial_account_value = self._strategy_val
        self._initial_coins = self._crypto_coins + (self._cash_value/price)
        self._initial_cash = (self._crypto_coins*price) + self._cash_value

    async def _get_portfolio_value(self, price):
        balance = await self._get_balance_cb()
        return balance['base']['available']*price + \
            balance['base']['hold']*price + \
            balance['quote']['available'] + \
            balance['quote']['hold']

    # Interface handlers
    def on_strategy_started(self):
        self._is_strategy_running = True

    def on_strategy_paused(self):
        self._is_strategy_running = False

    def reset_pnl_reference(self):
        log.info(
            'Resetting initial account value from {} to {}',
            self._initial_account_value, self._strategy_val)

        self._initial_account_value = self._strategy_val

    def update_reserves(self, delta_cash, delta_crypto):
        # log.info("Before Update: cash: {} crypto: {}".format(
        #     self._cash_value, self._crypto_coins))
        # log.info("Update Reserves delta cash: {}, delta crypto: {}".format(
        #     delta_cash, delta_crypto))

        self._cash_value += delta_cash
        self._crypto_coins += delta_crypto
        assert self._crypto_coins >= Decimal(0.0)
        assert self._cash_value >= Decimal(0.0)

        # log.info("After Update: cash: {} crypto: {}".format(
        #     self._cash_value, self._crypto_coins))

        if self._last_price != UNINITIALIZED:
            # Updating theoretical reserves as well
            self._initial_coins += delta_crypto + (delta_cash/self._last_price)
            self._initial_cash += delta_cash + (delta_crypto*self._last_price)

    def update_refresh_interval(self, interval):
        self._refresh_int = interval

    # Session Event Handlers
    def on_fill(self, order, filled_qty):
        # log.info("Before Fill: cash: {} crypto: {}".format(
        #     self._cash_value, self._crypto_coins))
        # log.info("Order: {}, filled_qty: {}".format(order, filled_qty))
        # Note: Assuming no taking, no fees
        self._num_traded += 1
        self._traded_qty += filled_qty

        if (order.side == Side.BUY or order.side == Side.BID):
            self._cash_value -= order.price * filled_qty
            self._crypto_coins += filled_qty
            if self._cash_value < Decimal(0.0):
                log.warning(
                        "Cash value is NEGATIVE. Curr: {}, Price: {}, Qty: {}".format(
                            self._cash_value, order.price, filled_qty))
                self._cash_value = 0
            if self._crypto_coins < Decimal(0.0):
                log.warning(
                        "Crypto is NEGATIVE. Curr: {}, Price: {}, Qty: {}".format(
                            self._crypto_coins, order.price, filled_qty))
                self._crypto_coins = 0
        else:
            self._cash_value += order.price * filled_qty
            self._crypto_coins -= filled_qty
            if self._cash_value < Decimal(0.0):
                log.warning(
                        "Cash value is NEGATIVE. Curr: {}, Price: {}, Qty: {}".format(
                            self._cash_value, order.price, filled_qty))
                self._cash_value = 0
            if self._crypto_coins < Decimal(0.0):
                log.warning(
                        "Crypto is NEGATIVE. Curr: {}, Price: {}, Qty: {}".format(
                            self._crypto_coins, order.price, filled_qty))
                self._crypto_coins = 0

        # log.info("After Fill: cash: {} crypto: {}".format(
        #     self._cash_value, self._crypto_coins))

    def apply_fees(self, side, price, fee):
        self._total_fees += fee
        if side == Side.BUY:
            self._crypto_coins -= (fee/price)
            assert self._crypto_coins >= Decimal(0.0)
        else:
            self._cash_value -= fee
            assert self._cash_value >= Decimal(0.0)

    def on_complete(self, order):
        pass

    # Helper methods
    def get_crypto_value(self, book=None):
        if book is None:
            assert self._last_price != UNINITIALIZED
            return self._crypto_coins*self._last_price

        mkt_price = self.get_mkt_price(book)
        return self._crypto_coins*mkt_price

    def get_cash_value(self):
        assert self._cash_value >= Decimal(0.0)
        return max(Decimal(0.0), self._cash_value)

    def get_strategy_value(self, book=None):
        return (self.get_crypto_value(book)) + Decimal(self._cash_value)

    def get_mkt_price(self, book):
        if hasattr(book, 'best_bid') and hasattr(book, 'best_ask'):
            return (book.best_bid.price + book.best_ask.price) / 2
        return (
            Decimal(book['bids'][0]['price']) +
            Decimal(book['asks'][0]['price'])) / 2

    # On book updates
    async def update(self, book):
        mkt_price = self.get_mkt_price(book)

        self._strategy_val = self.get_strategy_value(book)

        if self._initial_account_value == UNINITIALIZED:
            self._initialize(mkt_price)

        if self._is_strategy_running:
            state = StateColors['active']
        else:
            state = StateColors['halted']

        portfolio_value = await self._get_portfolio_value(mkt_price)
        net_pnl = round_to(self._strategy_val-self._initial_account_value)

        self._pnl = {
                       'mkt_price': mkt_price,
                       'strategy': round_to(self._strategy_val),
                       'starting': round_to(self._initial_account_value),
                       'cash': self._initial_cash,
                       'crypto': round_to(self._initial_coins*mkt_price),
                       'portfolio': round_to(portfolio_value),
                       'state': state,
                       'net': net_pnl,
                       'base': self._crypto_coins,
                       'quote': self._cash_value,
                       'num_traded': self._num_traded,
                       'traded_qty': self._traded_qty,
                       'instrument': self._instrument
                   }

    async def broadcast(self):
        log.info(
            'PnL at {}: [Strategy: {} - base: {}] | Portfolio: {}',
            self._pnl['mkt_price'],
            self._pnl['strategy'],
            self._pnl['net'],
            self._pnl['portfolio'])

        await self._broadcast_cb("update", "PnL", to_json(self._pnl))

    async def on_market_data(self, update):
        self._num_updates += 1
        if (self._num_updates >= self._refresh_int):
            self._num_updates = 0

            await self.update(update.book)
            await self.broadcast()
