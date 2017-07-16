import asyncio
import operator as op

from convex.common import Side, OrderedSet

from .exceptions import ReviseNack, CancelNack
from .limit_checker import LimitChecker


class Session:
    """Order session.

    Handle ownership of order.
    """
    def __init__(self, gateway, instrument, limits):
        self._gateway = gateway
        self._event_handlers = set()
        self._open_orders = OrderedSet()
        self._instrument = instrument
        self._limits = limits

    def add_event_handler(self, handler):
        self._event_handlers.add(handler)

    @property
    def limits(self):
        return self._limits

    @property
    def instrument(self):
        return self._instrument

    async def wait_ready(self):
        """Return when gateay is ready to submit orders."""
        await self._gateway.wait_ready()

    async def get_balances(self):
        """Get exchange base and quote balances.

        This method is a coroutine.

        Returns:
            (Decimal, Decimal): Base, quote currency balance tuple
        """
        base = await self.get_base_balance()
        quote = await self.get_quote_balance()
        return base, quote

    async def get_base_balance(self):
        """Get exchange account balance of base currency.

        This method is a coroutine.
        """
        balance = await self._gateway.get_balance(
            currency=self._instrument.base_currency)
        return balance

    async def get_quote_balance(self):
        """Get exchange account balance of quote currency.

        This method is a coroutine.
        """
        balance = await self._gateway.get_balance(
            currency=self._instrument.quote_currency)
        return balance

    async def exch_orders(self):
        """Get all exchange orders [open, pending, active]
        This method is a coroutine
        """
        return await self._gateway.exch_orders()

    async def get_fill(self, order_id):
        """Gets fill information for a specific order
        This method is a coroutine
        """
        return await self._gateway.get_fill(order_id)

    async def get_fills(self):
        """Gets all fills
        This method is a coroutine
        """
        return await self._gateway.get_fills()

    @property
    def long_position(self):
        return self._open_position(Side.BUY)

    @property
    def short_position(self):
        return self._open_position(Side.SELL)

    @property
    def open_orders(self):
        return self._open_orders

    @LimitChecker.submit_check
    async def submit(self, side, price, qty, ioc=False, quote=False):
        """Submit order.

        This method is a coroutine.

        Returns:
            Order: Object used to manage life of an order.
        """
        order = await self._gateway.submit(session=self,
                                           side=side,
                                           price=price,
                                           qty=qty,
                                           ioc=ioc,
                                           post_only=quote)

        if order.remaining_qty:
            self._open_orders.add(order)
        return order

    @LimitChecker.submit_check
    async def submit_ioc(self, side, price, qty):
        """Submit IOC order.

        This method is a coroutine.

        Returns:
            Order: Object used to manage life of an order.
        """
        return await self.submit(side=side,
                                 price=price,
                                 qty=qty,
                                 ioc=True)

    @LimitChecker.submit_check
    async def submit_quote(self, side, price, qty):
        """Submit a post-only resting order.

        This method is a coroutine.

        Returns:
            Order: Object used to manage life of an order.
        """
        return await self.session.submit(side=side,
                                         price=price,
                                         qty=qty,
                                         quote=True)

    def is_open(self, order):
        return order in self._open_orders

    async def cancel(self, order):
        """Cancel an order belonging to this session.

        This method is a coroutine.
        """
        if not self.is_open(order):
            raise CancelNack(order, 'Incorrect session or is not open')
        await self._gateway.cancel(order)

    async def revise(self, order, price=None, qty=None):
        """Revise price and/or quantity of an order.

        This method is a coroutine.
        """
        if not self.is_open(order):
            raise ReviseNack(order, 'Incorrect session or is not open')
        if qty and qty > order.remaining_qty:
            raise ReviseNack(order, 'Cannot increase revise quantity')
        await self._gateway.revise(order, price=price, qty=qty)

    async def cancel_session(self):
        """Cancel all orders for session.

        This method is a coroutine.
        """
        #TODO: There is a bug in this code somewhere...
        cancels = [self.cancel(order) for order in self.open_orders]
        await asyncio.gather(*cancels, loop=self._gateway.loop)


    async def cancel_all(self):
        """Cancels all orders at a global scale

        This method is a coroutine.
        """
        await self._gateway.cancel_all()


    def notify_fill(self, order, filled_qty):
        """Called when order is traded against."""
        if (order.session is self and
                order.remaining_qty and
                order not in self._open_orders):
            # Fill during submit action.
            self._open_orders.add(order)
        for handler in self._event_handlers:
            handler.on_fill(order, filled_qty)

    def notify_complete(self, order):
        """Called when order is no longer open."""
        self._open_orders.remove(order)
        for handler in self._event_handlers:
            handler.on_complete(order)

    def notify_all_complete(self):
        """Called when all orders are complete.

        Usually called on gateway-triggered cancel all.
        """
        for handler in self._event_handlers:
            for order in self._open_orders:
                handler.on_complete(order)
        self._open_orders.clear()

    def _open_position(self, side):
        GET_REMAINING = op.attrgetter('remaining_qty')
        orders = filter(lambda o: o.side == side, self.open_orders)
        return sum(map(GET_REMAINING, orders))
