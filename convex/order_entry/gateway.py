import asyncio
import abc

from .order import Order


class Gateway(metaclass=abc.ABCMeta):
    """Base order gateway."""
    def __init__(self, loop):
        self._loop = loop
        self._oid_sessions = {}  # Order ID -> Session

    @property
    def loop(self):
        """Event loop."""
        return self._loop

    @property
    def sessions(self):
        """Known sessions."""
        return set(self._oid_sessions.values())

    async def submit(
            self, session,
            side, price, qty,
            ioc=False,
            post_only=False):
        """Submit order.

        This method is a coroutine.
        """
        if ioc and post_only:
            raise ValueError('Cannot send post-only and IOC')
        order_id = await self.send_order(side=side,
                                         price=price,
                                         qty=qty,
                                         ioc=ioc,
                                         post_only=post_only)
        self._oid_sessions[order_id] = session
        return Order(session=session,
                     order_id=order_id,
                     price=price,
                     remaining_qty=qty)

    async def cancel(self, order):
        """Cancel order.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """
        await self.send_cancel(order)
        sess = self._oid_sessions.pop(order.order_id)
        sess.notify_complete(order)

    async def revise(self, order, price=None, qty=None):
        """Revise order.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """
        await self.send_revise(order, price=price, qty=qty)

    async def cancel_all(self):
        """Cancel all orders.

        This method is a coroutine.
        """
        try:
            await self.send_cancel_all()
            for sess in self.sessions:
                sess.notify_all_complete()
        except NotImplementedError:
            cancels = [sess.cancel_all() for sess in self.sessions]
            await asyncio.gather(cancels, loop=self.loop)

    @abc.abstractmethod
    async def send_order(self, side, price, qty, ioc, post_only):
        """Send message for new order.

        This method must be overriden by dereived class.

        This method is a coroutine.

        Returns:
            Exchange specific order ID.
        """

    @abc.abstractmethod
    async def send_revise(self, order, price, qty):
        """Send message to revise order.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """

    @abc.abstractmethod
    async def send_cancel(self, order):
        """Send message to cancel order.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """
    async def send_cancel_all(self):
        """Send message to cancel all orders.

        This method is optionally overriden by dereived class.

        This method is a coroutine.
        """
        raise NotImplementedError()
