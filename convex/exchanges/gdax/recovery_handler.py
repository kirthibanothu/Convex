import collections
from decimal import Decimal

import aiohttp

from market_data import OrderBasedBook
from common.side import Side


class RecoveryHandler:
    ENDPOINT = 'https://api.gdax.com'

    def __init__(self, loop):
        self._loop = loop
        self._message_queue = collections.deque()
        self._sequence = 0

    async def fetch_snapshot(self, inst):
        """Request book snapshot.

        Returns:
            int, OrderBasedBook: Sequence number and book snapshot.
        """
        with aiohttp.ClientSession(loop=self._loop) as session:
            seq, book = await RecoveryHandler._request_book(session, inst)
            self._sequence = seq
            return seq, book

    def drop_stored(self):
        self._message_queue.clear()

    def store_message(self, message):
        self._message_queue.append(message)

    def apply_messages(self, apply_cb):
        messages = self._message_queue
        print('Applying recovery {} message(s)'.format(len(messages)))
        while messages:
            message = messages.pop()
            mseq = int(message['sequence'])
            if mseq > self._sequence:
                apply_cb(message)

    @staticmethod
    async def _request_book(sess, inst):
        """Request full book.

        Returns:
            int, OrderBasedBook: Sequence number and book snapshot.
        """
        ORDER_BOOK_EP = RecoveryHandler.ENDPOINT + '/products/{}/book'
        BOOK_LEVEL = 3
        endpoint = ORDER_BOOK_EP.format(inst)
        async with sess.get(endpoint, params={'level': BOOK_LEVEL}) as res:
            data = await res.json()
            seq = int(data['sequence'])
            return seq, RecoveryHandler._parse_book_data(data)

    @staticmethod
    def _parse_book_data(data):
        book = OrderBasedBook()

        def add_parsed_order(side, odata):
            oid = odata[2]
            px = Decimal(odata[0])
            qty = Decimal(odata[1])
            book.add_order(side=side, order_id=oid, price=px, qty=qty)

        for bid_data in data['bids']:
            add_parsed_order(Side.BID, bid_data)
        for ask_data in data['asks']:
            add_parsed_order(Side.ASK, ask_data)
        return book
