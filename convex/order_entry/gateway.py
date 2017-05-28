import asyncio
import abc

import logbook

log = logbook.Logger('OE')


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

    @abc.abstractmethod
    async def wait_ready(self):
        """Return when gateway is ready to submit orders.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """

    @abc.abstractmethod
    async def get_balance(self, currency):
        """Get exchange account balance for currency.

        This method must be overriden by dereived class.

        THis method is a coroutine.
        """

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
        order = await self.send_order(session=session,
                                      side=side,
                                      price=price,
                                      qty=qty,
                                      ioc=ioc,
                                      post_only=post_only)
        if order.filled_qty:
            session.notify_fill(order, order.filled_qty)
        self._oid_sessions[order.order_id] = session
        return order

    async def cancel(self, order):
        """Cancel order.

        This method must be overriden by dereived class.

        This method is a coroutine.
        """
        await self.send_cancel(order)
        try:
            sess = self._oid_sessions.pop(order.order_id)
        except KeyError:
            log.warning('Cancelled order for unknown session')
        else:
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

    def on_fill(self, order, filled_qty):
        if not order.remaining_qty:
            return self._on_complete_fill(order, filled_qty)

        try:
            session = self._oid_sessions[order.order_id]
        except KeyError:
            log.error('Fill for unknown session: filled_qty={}, order={}',
                      filled_qty, order)
            asyncio.ensure_future(self.cancel(order))
        else:
            session.on_fill(order, filled_qty)

    def _on_complete_fill(self, order, filled_qty):
        try:
            session = self._oid_sessions.pop(order.order_id)
        except KeyError:
            log.error('Complete fill for unknown session: ' +
                      'filled_qty={}, order={}', filled_qty, order)
        else:
            session.on_fill(order, filled_qty)
            session.on_complete(order)

    @abc.abstractmethod
    async def send_order(self, side, price, qty, ioc, post_only):
        """Send message for new order.

        This method must be overriden by dereived class.

        This method is a coroutine.

        Returns:
            Order object
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
