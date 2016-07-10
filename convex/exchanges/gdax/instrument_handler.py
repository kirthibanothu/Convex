import logbook
import dateutil.parser as du_parser

from ...market_data import Status, Update, Trade, OrderBasedBook

from ...common import Side, make_price, make_qty

log = logbook.Logger('GDAX')


class InstrumentHandler:
    def __init__(self, instrument):
        self._instrument = instrument
        self._book = OrderBasedBook()
        self._sequence = 0
        self._timestamp_str = ''
        self._trades = []
        self._pending_book_id = 0

        self._message_handlers = {
                'open': self._handle_open_message,
                'change': self._handle_change_message,
                'done': self._handle_done_message,
                'match': self._handle_match_message,
                'received': lambda m: False
        }

    def recover(self, sequence, book):
        self._sequence = sequence
        self._book = book
        self._set_pending_book_id()

    @property
    def _pending_update(self):
        return self._pending_book_id != 0 or self._trades

    @property
    def _timestamp(self):
        try:
            return du_parser.parse(self._timestamp_str)
        except ValueError:
            log.warn('Cannot parse timestamp "{}"', self._timestamp_str)
            return None

    def _fetch_pending_book_id(self):
        if self._pending_book_id != 0:
            book_id = self._pending_book_id
            self._pending_book_id = 0
            return book_id
        if self._trades:
            return self._trades[0].book_id
        return self._sequence

    def _fetch_pending_trades(self):
        trades = self._trades.copy()
        self._trades.clear()
        return trades

    def make_update(self):
        if not self._pending_update:
            return None

        book_id = self._fetch_pending_book_id()
        book = self._book.make_book(book_id=book_id)
        trades = self._fetch_pending_trades()
        return Update(
                instrument=self._instrument,
                book=book,
                trades=trades,
                status=Status.OK,
                timestamp=self._timestamp)

    def make_gapped_update(self):
        return Update(
                instrument=self._instrument,
                book=self._book.make_book(book_id=self._sequence),
                trades=self._fetch_pending_trades(),
                status=Status.GAPPED,
                timestamp=self._timestamp)

    def handle_message(self, message):
        sequence = int(message['sequence'])
        if sequence <= self._sequence:
            return
        self._sequence = sequence
        self._timestamp_str = message['time']

        message_type = message['type']
        try:
            cb = self._message_handlers[message_type]
            updated_book = cb(message)
            if updated_book:
                self._set_pending_book_id()
        except KeyError:
            log.exception('Unhandled message type: {}', message)

    def _set_pending_book_id(self):
        self._pending_book_id = self._sequence

    def _handle_open_message(self, message):
        self._book.add_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                qty=make_qty(message['remaining_size']))
        return True

    @staticmethod
    def _parse_trade(message):
        resting_side = Side.parse(message['side'])
        return Trade(
                aggressor=resting_side.opposite,
                price=make_price(message['price']),
                qty=make_qty(message['size']),
                book_id=int(message['sequence']))

    def _handle_match_message(self, message):
        trade = InstrumentHandler._parse_trade(message)
        self._book.match_order(
                side=trade.aggressor.opposite,
                order_id=message['maker_order_id'],
                price=trade.price,
                trade_qty=trade.qty)
        self._trades.append(trade)
        return True

    def _handle_done_message(self, message):
        price = message.get('price', None)
        if not price:
            # Market orders do not have a price field
            return
        removed = self._book.remove_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(price))
        return removed

    def _handle_change_message(self, message):
        if 'new_funds' in message:
            # Changed market orders use "funds" fields.
            return
        changed = self._book.change_order(
                side=Side.parse(message['side']),
                order_id=message['order_id'],
                price=make_price(message['price']),
                new_qty=make_qty(message['new_size']))
        return changed