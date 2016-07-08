from decimal import Decimal
import json
import asyncio

import websockets

from market_data import Update, OrderBasedBook
from market_data.gateway import Gateway as BaseGateway

from common.side import Side

from .recovery_handler import RecoveryHandler


class Gateway(BaseGateway):
    ENDPOINT = 'https://api.gdax.com'
    WS_ENDPOINT = 'wss://ws-feed.gdax.com'
    REQS_PER_SEC = 3.0

    def __init__(self, loop=None):
        BaseGateway.__init__(self, loop)
        self._instruments = set()
        self._in_recovery = False
        self._book = OrderBasedBook()
        self._sequence = 0
        self._recovery_handler = RecoveryHandler(loop=self._loop)
        self._recovery_task = None
        self._in_sequence = 0
        self._message_handlers = {
                'open': self._handle_open_message,
                'change': self._handle_change_message,
                'done': self._handle_done_message,
                'match': self._handle_match_message,
                'received': lambda m: False
        }

    def subscribe(self, instrument):
        assert(instrument == 'BTC-USD')
        self._instruments.add(instrument)

    @property
    def in_recovery(self):
        return self._recovery_task is not None

    async def launch(self):
        if not self._instruments:
            raise ValueError('No subscribed instruments')
        async with websockets.connect(
                Gateway.WS_ENDPOINT,
                loop=self._loop) as sock:
            for inst in self._instruments:
                await Gateway._send_subscribe(sock, inst)
            while True:
                data = await sock.recv()
                message = json.loads(data)
                gapped = not self._check_sequence(message)
                if gapped:
                    self._handle_gap()
                elif self.in_recovery:
                    self._recovery_handler.store_message(message)
                else:
                    self._handle_message(message)

    @staticmethod
    async def _send_subscribe(sock, inst):
        message = json.dumps({'type': 'subscribe', 'product_id': inst})
        print('Subscribing: {}'.format(message))
        await sock.send(message)

    def _check_sequence(self, message):
        seq = int(message['sequence'])
        if seq <= self._in_sequence:
            return True
        valid = (seq == self._in_sequence + 1)
        self._in_sequence = seq
        return valid

    def _handle_message(self, message):
        sequence = int(message['sequence'])
        if sequence <= self._sequence:
            return
        self._sequence = sequence
        cb = self._message_handlers.get(message['type'], None)
        if not cb:
            print('Unhandled message type:', message)
            return

        updated = cb(message)
        if updated and not self.in_recovery:
            inst = next(iter(self._instruments))
            book = self._book.make_book(sequence)
            update = Update(instrument=inst, book=book)
            asyncio.ensure_future(
                    self._publish_update(update),
                    loop=self._loop)

    def _parse_side(self, side):
        return Side.BUY if side == 'buy' else Side.SELL

    def _handle_open_message(self, message):
        self._book.add_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=Decimal(message['price']),
                qty=Decimal(message['remaining_size']))
        return True

    def _handle_match_message(self, message):
        resting_side = self._parse_side(message['side'])
        resting_oid = message['maker_order_id']
        self._book.match_order(
                side=resting_side,
                order_id=resting_oid,
                price=Decimal(message['price']),
                trade_qty=Decimal(message['size']))
        # TODO Add trade to update.
        print('Trade! {side} -- {size} @ {price}'.format(**message))
        return True

    def _handle_done_message(self, message):
        price = message.get('price', None)
        if not price:
            # Market orders do not have a price field
            return False
        return self._book.remove_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=Decimal(price))

    def _handle_change_message(self, message):
        if 'new_funds' in message:
            # Changed market orders use "funds" fields.
            return False
        return self._book.change_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=Decimal(message['price']),
                new_qty=Decimal(message['new_size']))

    def _handle_gap(self):
        if self._recovery_task:
            print('Gap detected during recovery')
            self._recovery_task.cancel()
        else:
            print('Gap detected')
        self._recovery_handler.drop_stored()
        self._recovery_task = asyncio.ensure_future(
                self._start_recovery(),
                loop=self._loop)

    async def _start_recovery(self):
        inst = next(iter(self._instruments))
        snapshot = await self._recovery_handler.fetch_snapshot(inst)
        print('Post-gap: ', snapshot)
        self._sequence, self._book = snapshot
        self._recovery_handler.apply_messages(self._handle_message)
        self._recovery_task = None
