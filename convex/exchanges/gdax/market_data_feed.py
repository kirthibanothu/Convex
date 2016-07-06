from decimal import Decimal
import asyncio
import collections
import json

import aiohttp
import websockets

from market_data import Update, OrderBasedBook
from market_data.gateway import Gateway as BaseGateway


class Gateway(BaseGateway):
    ENDPOINT = 'https://api.gdax.com'
    WS_ENDPOINT = 'wss://ws-feed.gdax.com'
    REQS_PER_SEC = 3.0

    def __init__(self, loop=None):
        BaseGateway.__init__(self, loop)
        self._instruments = set()
        self._in_recovery = True
        self._recovery_queue = collections.deque()
        self._book = OrderBasedBook()
        self._prev_seq_num = 0

    def subscribe(self, instrument):
        assert(instrument == 'BTC-USD')
        self._instruments.add(instrument)

    async def launch(self):
        if not self._instruments:
            raise ValueError('No subscribed instruments')
        async with websockets.connect(
                Gateway.WS_ENDPOINT,
                loop=self._loop) as sock:
            for inst in self._instruments:
                await Gateway._send_subscribe(sock, inst)
        with aiohttp.ClientSession(loop=self._loop) as session:
                await self._poll(session)
                sleep_s = 2.0 * len(self._instruments) / Gateway.REQS_PER_SEC
                await asyncio.sleep(sleep_s)

    @staticmethod
    async def _send_subscribe(sock, inst):
        message = {'type': 'subscribe', 'product_id': inst}
        await sock.send(json.dumps(message))

    def _on_recovery_message(self, message):
        self._book.clear()
        while self._recovery_queue:
            message = self._recovery_queue.pop()
            self._on_message(message, publish=False)

    def _on_message(self, message, publish=True):
        if self._in_recovery:
            self._recovery_queue.append(message)
            return
