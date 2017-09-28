import asyncio
from datetime import datetime
import dateutil.parser as du_parser
from logger import log

from convex.market_data import Status
from convex.common import make_qty


TRADE_IMPACT = 'Trade impacted one of our outstanding orders'


class BasicOrderManager():
    '''
        Need to feed the order manager market data:
            The on_market_data callback
        Will update the state of the session's orders if it notices
        any of the strategy's orders are impacted.
        In the case of a gap, it will try and fetch all fills for
        the session's open orders in order to reconsiliate any missed events
    '''
    def __init__(self, session):
        self._session = session
        self._last_update_ts = datetime.now()

    async def get_order_fill_pair(self, order):
        order_fills = []

        fills = await self._session.get_fill(order.order_id)

        # Gather all relevant fills since last update
        for fill in fills:
            if du_parser.parse(fill['created_at']) > self._last_update_ts:
                order_fills.append([order, fill])

        return order_fills

    async def on_gap(self):
        # Need to manually update the state of every order in existance
        log.warn('Gapped! Need to request fill status of all orders')

        tasks = []
        for open_order in self._session.open_orders:
            task = asyncio.ensure_future(
                    self._session.get_fill(open_order.order_id))
            tasks.append(task)

        order_fill_pairs = await asyncio.gather(*tasks)

        for pairs in order_fill_pairs:
            for pair in pairs:
                order = pair[0]
                fill = pair[1]
                log.info(
                    'Apply fill found after gap: [Order-{}], [Fill-{}]',
                    order, fill)

                self._session.on_order_fill(
                    order, make_qty(fill['size']))

                if order.remaining_qty == 0:
                    self._session.notify_complete(order)

    def apply_trade(self, order, trade, side):
        # Trade impacted one of our outstanding orders!
        log.info('{} [{}] - {}', TRADE_IMPACT, trade, side)
        self._session.on_order_fill(order, trade.qty)

        if order.remaining_qty == 0:
            self._session.notify_complete(order)

    def update_orders(self, update):
        # Check the trades to see if our order ids are in there
        order_mapping = {
            o.order_id: o for o in self._session.open_orders
        }

        trades = update.trades
        for trade in trades:
            if trade.maker_id in order_mapping:
                self.apply_trade(order_mapping[trade.maker_id], trade, 'maker')
            elif trade.taker_id in order_mapping:
                self.apply_trade(order_mapping[trade.taker_id], trade, 'taker')

    async def on_market_data(self, update):
        if (update.status == Status.GAPPED):
            await self.on_gap()
        else:
            self.update_orders(update)

        self._last_update_ts = update.timestamp
