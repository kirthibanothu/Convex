from common import make_price, make_qty


class Order:
    def __init__(self, session, order_id, price=None, remaining_qty=None):
        self._session = session
        self._order_id = order_id
        self.price = price if price else make_price(0)
        self.remaining_qty = remaining_qty if remaining_qty else make_qty(0)

    @property
    def order_id(self):
        """Exchange specific order ID."""
        return self._order_id

    @property
    def is_open(self):
        """Is open order."""
        return self._session.is_open(order=self)

    async def revise(self, price=None, qty=None):
        """Revise price or quantity of order.

        This method is a coroutine.
        """
        await self._session.revise(order=self, price=price, qty=qty)

    async def cancel(self):
        """Cancel order.

        This method is a coroutine.
        """
        await self._session.cancel(order=self)
