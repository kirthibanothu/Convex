import collections

import aiohttp
import logbook

from ...market_data import OrderBasedBook
from ...common import Side, make_price, make_qty

log = logbook.Logger('GDAX')


class RecoveryHandler:
    ENDPOINT = 'https://api.gdax.com'

    def __init__(self, loop):
        self._loop = loop
        self._message_queue = collections.deque()
        self._sequence = 0

    async def fetch_snapshot(self, product_id):
        """Request book snapshot.

        Returns:
            int, OrderBasedBook: Sequence number and book snapshot.
        """
        with aiohttp.ClientSession(loop=self._loop) as session:
            seq, book = await RecoveryHandler._request_book(session,
                                                            product_id)
            self._sequence = seq
            return seq, book

    def drop_stored(self):
        self._message_queue.clear()

    def store_message(self, message):
        self._message_queue.append(message)

    def apply_messages(self, apply_cb):
        messages = self._message_queue
        applied_count = 0

        while messages:
            message = messages.popleft()
            mseq = int(message['sequence'])
            if mseq > self._sequence:
                log.debug('Applying sequence={}', mseq)
                apply_cb(message)
                applied_count += 1
        log.info('Applied {} recovery message(s)', applied_count)

    @staticmethod
    async def _request_book(sess, product_id):
        """Request full book.

        Returns:
            int, OrderBasedBook: Sequence number and book snapshot.
        """
        ORDER_BOOK_EP = RecoveryHandler.ENDPOINT + '/products/{}/book'
        BOOK_LEVEL = 3
        endpoint = ORDER_BOOK_EP.format(product_id)
        async with sess.get(endpoint, params={'level': BOOK_LEVEL}) as res:
            data = await res.json()
            seq = int(data['sequence'])
            return seq, RecoveryHandler._parse_book_data(data)

    @staticmethod
    def _parse_book_data(data):
        book = OrderBasedBook()

        def add_parsed_order(side, odata):
            oid = odata[2]
            px = make_price(odata[0])
            qty = make_qty(odata[1])
            book.add_order(side=side, order_id=oid, price=px, qty=qty)

        for bid_data in data['bids']:
            add_parsed_order(Side.BID, bid_data)
        for ask_data in data['asks']:
            add_parsed_order(Side.ASK, ask_data)
        return book
