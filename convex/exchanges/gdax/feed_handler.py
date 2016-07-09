import logbook

from market_data import Update, OrderBasedBook

from common.side import Side
from common.price import make_price, make_qty

log = logbook.Logger('GDAX')


class FeedHandler:
    def __init__(self, instrument):
        self._instrument = instrument
        self._book = OrderBasedBook()
        self._sequence = 0
        self._message_handlers = {
                'open': self._handle_open_message,
                'change': self._handle_change_message,
                'done': self._handle_done_message,
                'match': self._handle_match_message,
                'received': lambda m: False
        }
        self._pending_update = False

    def recover(self, sequence, book):
        self._sequence = sequence
        self._book = book

    def make_update(self):
        if not self._pending_update:
            return None
        book = self._book.make_book(self._sequence)
        self._pending_update = False
        return Update(instrument=self._instrument, book=book)

    def handle_message(self, message):
        sequence = int(message['sequence'])
        if sequence <= self._sequence:
            return
        self._sequence = sequence
        cb = self._message_handlers.get(message['type'], None)
        if not cb:
            log.error('Unhandled message type:', message)
            return

        updated = cb(message)
        self._pending_update = self._pending_update or updated

    def _parse_side(self, side):
        return Side.BUY if side == 'buy' else Side.SELL

    def _handle_open_message(self, message):
        self._book.add_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                qty=make_qty(message['remaining_size']))
        return True

    def _handle_match_message(self, message):
        resting_side = self._parse_side(message['side'])
        resting_oid = message['maker_order_id']
        self._book.match_order(
                side=resting_side,
                order_id=resting_oid,
                price=make_price(message['price']),
                trade_qty=make_qty(message['size']))
        # TODO Add trade to update.
        log.info('Trade! {side} -- {size} @ {price}'.format(**message))
        return True

    def _handle_done_message(self, message):
        price = message.get('price', None)
        if not price:
            # Market orders do not have a price field
            return False
        return self._book.remove_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=make_price(price))

    def _handle_change_message(self, message):
        if 'new_funds' in message:
            # Changed market orders use "funds" fields.
            return False
        return self._book.change_order(
                side=self._parse_side(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                new_qty=make_qty(message['new_size']))
