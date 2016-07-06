import asyncio
from decimal import Decimal

import aiohttp

from market_data import Book, Update, Level
from market_data.gateway import Gateway as BaseGateway


class Gateway(BaseGateway):
    ENDPOINT = 'https://api.gdax.com'
    REQS_PER_SEC = 3.0

    def __init__(self, loop=None):
        BaseGateway.__init__(self, loop)
        self._instruments = set()

    def subscribe(self, instrument):
        assert(instrument == 'BTC-USD')
        self._instruments.add(instrument)

    async def launch(self):
        if not self._instruments:
            raise ValueError('No subscribed instruments')
        with aiohttp.ClientSession(loop=self._loop) as session:
            while True:
                await self._poll(session)
                sleep_s = 2.0 * len(self._instruments) / Gateway.REQS_PER_SEC
                await asyncio.sleep(sleep_s)

    async def _poll(self, sess):
        reqs = [self._poll_book(sess, inst) for inst in self._instruments]
        await asyncio.wait(reqs, return_when=asyncio.FIRST_COMPLETED)

    async def _poll_book(self, sess, inst):
        ORDER_BOOK_EP = Gateway.ENDPOINT + '/products/{}/book'
        BOOK_LEVEL = 1
        endpoint = ORDER_BOOK_EP.format(inst)
        data = await Gateway._poll_endpoint(
                sess, endpoint,
                params={'level': BOOK_LEVEL})
        update = Update(instrument=inst, book=Gateway._parse_book(data))
        await self._publish_update(update)

    async def _poll_trades(self, sess, inst):
        TRADE_EP = Gateway.ENDPOINT + '/products/{}/trades'
        endpoint = TRADE_EP.format(inst)
        await Gateway._poll_endpoint(sess, endpoint)

    @staticmethod
    async def _poll_endpoint(sess, endpoint, params=None):
        async with sess.get(endpoint, params=params) as res:
            return await res.json()

    @staticmethod
    def _parse_book(res):
        def parse_side(s):
            px, qty, orders = Decimal(s[0]), Decimal(s[1]), int(s[2])
            return Level(price=px, qty=qty, orders=orders)

        res_bids, res_asks = res['bids'], res['asks']
        return Book(
                book_id=int(res['sequence']),
                bids=[parse_side(b) for b in res_bids],
                asks=[parse_side(a) for a in res_asks])
