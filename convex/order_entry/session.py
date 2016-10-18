import collections
import asyncio


class Session:
    """Order session.

    Handle ownership of order.
    """
    def __init__(self, gateway, event_handler=None):
        self._gateway = gateway
        self._event_handler = event_handler
        self._open_orders = collections.OrderedDict()  # Order ID -> Order

    async def submit(self, side, price, qty):
        """Submit resting order.

        This method is a coroutine.

        Returns:
            Order: Object used to manage life of an order.
        """
        order = await self._gateway.submit(session=self,
                                           side=side,
                                           price=price,
                                           qty=qty)
        self._open_orders[order.order_id] = order
        return order

    async def submit_quote(self, side, price, qty):
        """Submit a post-only resting order.

        This method is a coroutine.

        Returns:
            Order: Object used to manage life of an order.
        """
        order = await self._gateway.submit(session=self,
                                           side=side,
                                           price=price,
                                           qty=qty,
                                           post_only=True)
        self._open_orders[order.order_id] = order
        return order

    def is_open(self, order):
        return order.order_id in self._open_orders

    async def cancel(self, order):
        """Cancel an order belonging to this session.

        This method is a coroutine.
        """
        if self.is_open(order):
            # TODO: Use different error
            raise KeyError('Order belongs to different session or is not open')
        await self._gateway.cancel(order)
        self.notify_complete(order)

    async def revise(self, order, price=None, qty=None):
        """Revise price and/or quantity of an order.

        This method is a coroutine.
        """
        if self.is_open(order):
            # TODO: Use different error
            raise KeyError('Order belongs to different session or is not open')
        await self._gateway.revise(order, price=price, qty=qty)

    async def cancel_all(self):
        """Cancel all orders for session.

        This method is a coroutine.
        """
        cancels = [self.cancel(order) for order in self._open_orders.values()]
        await asyncio.gather(cancels, loop=self._gateway.loop)

    def notify_fill(self, order, filled_qty):
        """Called when order is traded against."""
        if self._event_handler:
            self._event_handler.on_fill(order, filled_qty)

    def notify_complete(self, order):
        """Called when order is no longer open."""
        del self._open_orders[order.order_id]
        if self._event_handler:
            self._event_handler.on_complete(order)

    def notify_all_complete(self):
        """Called when all orders are complete.

        Usually called on gateway-triggered cancel all.
        """
        for order in self._open_orders:
            self._event_handler.on_complete(order)
        self._open_orders.clear()
