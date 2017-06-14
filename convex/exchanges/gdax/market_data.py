try:
    import ujson as json
except ImportError:
    import json

import asyncio

import aiohttp
import dateutil.parser as du_parser
import logbook
import websockets

from ..exchange_id import ExchangeID

from ...common import Side, make_price, make_qty
from ...common.instrument import make_btc_usd, make_ltc_usd, make_eth_usd
from ... import market_data

from .common import make_symbol as make_gdax_symbol

log = logbook.Logger('GDAX')


class MDGateway(market_data.Gateway):
    ENDPOINT = 'https://api.gdax.com'
    WS_ENDPOINT = 'wss://ws-feed.gdax.com'

    def __init__(self,
                 endpoint=ENDPOINT,
                 ws_endpoint=WS_ENDPOINT,
                 loop=None):
        market_data.Gateway.__init__(self, loop)
        self._endpoint = endpoint
        self._ws_endpoint = ws_endpoint
        self._sequence = -1
        self._message_queue = asyncio.Queue(loop=self.loop)
        self._dispatch_map = {
            'open': self._handle_open_message,
            'change': self._handle_change_message,
            'done': self._handle_done_message,
            'match': self._handle_match_message,
            'received': lambda m: False
        }
        self._is_running = True
        self._shutdown_evt = asyncio.Event(loop=loop)

    def subscribe(self, instrument):
        if instrument != make_btc_usd(ExchangeID.GDAX) and instrument != make_ltc_usd(ExchangeID.GDAX) and instrument != make_eth_usd(ExchangeID.GDAX):
            raise ValueError('Unsupported instrument: {}'.format(instrument))
        self._instrument = instrument

    @property
    def _product_id(self):
        return make_gdax_symbol(self._instrument)

    @property
    def exchange_id(self):
        """Exchange ID"""
        return ExchangeID.GDAX

    async def launch(self):
        if not self._instrument:
            raise ValueError('No subscribed instruments')

        tasks = [
            self._consume_messages(),
            self._poll_endpoint(self._ws_endpoint),
            self._shutdown_evt.wait()
        ]
        done, pending = await asyncio.wait(tasks,
                                           loop=self.loop,
                                           return_when=asyncio.FIRST_COMPLETED)
        log.notice('Shutting down')
        for p in pending:
            p.cancel()

    def request_shutdown(self):
        log.notice('Shutdown requested')
        self._is_running = False
        self._shutdown_evt.set()

    async def _poll_queue(self):
        m0 = await self._message_queue.get()
        log.debug('Pull size {}', self._message_queue.qsize() + 1)
        messages = [m0]
        while not self._message_queue.empty():
            messages.append(self._message_queue.get_nowait())
        return messages

    async def _consume_messages(self):
        while self._is_running:
            messages = await self._poll_queue()
            has_update = False
            for m in map(json.loads, messages):
                new_update = await self._on_message(m)
                has_update = has_update or new_update
            if has_update:
                self.set_book(self._instrument, self._sequence, self._book)
                self.publish()

    async def _poll_endpoint(self, endpoint):
        async def send_subscribe(sock):
            message = json.dumps(
                    {'type': 'subscribe', 'product_id': self._product_id})
            log.info('Subscribing: {}', message)
            await sock.send(message)

        try:
            async with websockets.connect(endpoint, loop=self.loop) as sock:
                try:
                    await send_subscribe(sock)
                    while self._is_running:
                        data = await sock.recv()
                        self._message_queue.put_nowait(data)
                        log.debug('Push size {}', self._message_queue.qsize())
                except asyncio.CancelledError:
                    log.notice('Canceled poll_endpoint')
        except:
            log.exception()

    async def _on_message(self, message):
        recv_seq = int(message['sequence'])
        if recv_seq > self._sequence + 1:
            log.info('Gap detected received {}, expected {}',
                     recv_seq, self._sequence + 1)

            self.set_status(self._instrument, market_data.Status.GAPPED)
            self.publish()

            self._message_queue = asyncio.Queue(loop=self.loop)
            self._sequence = await self._recover()

            log.info('Recover sequence {}', self._sequence)
            self.set_status(self._instrument, market_data.Status.OK)

        if recv_seq <= self._sequence:
            return False

        self.set_timestamp(du_parser.parse(message['time']))
        assert recv_seq == self._sequence + 1
        self._sequence = recv_seq
        return self._dispatch_message(message)

    def _dispatch_message(self, message):
        return self._dispatch_map[message['type']](message)

    def _handle_open_message(self, message):
        self._book.add_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                qty=make_qty(message['remaining_size']))
        return True

    def _handle_match_message(self, message):
        trade = MDGateway._parse_trade(message)
        self.add_trade(self._instrument, trade)
        self._book.match_order(
                side=trade.aggressor.opposite,
                order_id=message['maker_order_id'],
                price=trade.price,
                trade_qty=trade.qty)
        return True

    def _handle_done_message(self, message):
        price = message.get('price', None)
        if not price:
            return False  # Market orders do not have a price field
        removed = self._book.remove_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(price))
        return removed

    def _handle_change_message(self, message):
        if 'new_funds' in message:
            return  # Changed market orders use "funds" fields.
        changed = self._book.change_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                new_qty=make_qty(message['new_size']))
        return changed

    @staticmethod
    def _parse_trade(message):
        resting_side = Side.parse(message['side'])
        return market_data.Trade(
                aggressor=resting_side.opposite,
                price=make_price(message['price']),
                qty=make_qty(message['size']),
                sequence=int(message['sequence']))

    async def _recover(self):
        with aiohttp.ClientSession(loop=self.loop) as session:
            order_book_ep_fmt = self._endpoint + '/products/{}/book'
            endpoint = order_book_ep_fmt.format(self._product_id)
            log.info('Recovering on {}', endpoint)
            async with session.get(endpoint, params={'level': 3}) as res:
                snapshot = await res.json()
                self._book = MDGateway._on_snapshot(snapshot)
                return snapshot['sequence']

    @staticmethod
    def _on_snapshot(message):
        book = market_data.OrderBasedBook()

        def add_parsed_order(side, odata):
            book.add_order(side=side,
                           order_id=odata[2],
                           price=make_price(odata[0]),
                           qty=make_qty(odata[1]))

        for bid_data in message['bids']:
            add_parsed_order(Side.BID, bid_data)
        for ask_data in message['asks']:
            add_parsed_order(Side.ASK, ask_data)
        return book
