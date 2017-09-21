from ..common import make_price, make_qty


class Order:
    def __init__(self,
                 session,
                 order_id,
                 side,
                 price=None,
                 original_qty=None,
                 remaining_qty=None,
                 filled_qty=None):
        self._session = session
        self._order_id = order_id
        self.side = side
        self.price = price or make_price(0)
        self.original_qty = original_qty or make_qty(0)
        self.remaining_qty = remaining_qty or make_qty(0)
        self.filled_qty = filled_qty or make_qty(0)

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

    def dump(self):
        return {
            'side': self.side.name,
            'order_id': self.order_id,
            'price': str(self.price),
            'remaining_qty': str(self.remaining_qty)
        }

    def __hash__(self):
        return hash(self._order_id)

    def __eq__(self, other):
        return self._order_id == other._order_id

    def __str__(self):
        return '{} {}@{}, order_id={}'.format(
                self.side.name,
                self.price,
                self.remaining_qty,
                self.order_id)
