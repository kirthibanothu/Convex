import json
import asyncio

import logbook
import websockets

from market_data.gateway import Gateway as BaseGateway

from .recovery_handler import RecoveryHandler
from .feed_handler import FeedHandler

log = logbook.Logger('GDAX')


class Gateway(BaseGateway):
    ENDPOINT = 'https://api.gdax.com'
    WS_ENDPOINT = 'wss://ws-feed.gdax.com'
    REQS_PER_SEC = 3.0

    def __init__(self, loop=None):
        BaseGateway.__init__(self, loop)
        self._recovery_handler = RecoveryHandler(loop=self.loop)
        self._recovery_task = None
        self._in_sequence = 0
        self._message_queue = asyncio.Queue(loop=self.loop)

    def subscribe(self, instrument):
        assert(instrument == 'BTC-USD')
        self._instrument = instrument
        self._inst_handler = FeedHandler(instrument)

    @property
    def in_recovery(self):
        return self._recovery_task is not None

    async def launch(self):
        if not self._instrument:
            raise ValueError('No subscribed instruments')

        await asyncio.gather(
                self._poll_endpoint(Gateway.WS_ENDPOINT),
                self._consume_messages(),
                loop=self.loop)

    def _on_message(self, message):
        if not self._check_sequence(message):
            return
        if self.in_recovery:
            self._recovery_handler.store_message(message)
        else:
            self._inst_handler.handle_message(message)

    def _clear_queue(self):
        while not self._message_queue.empty():
            self._message_queue.get_nowait()

    async def _consume_messages(self):
        try:
            await self._consume_messages_impl()
        except asyncio.CancelledError:
            log.warn('Canceled consume_messages')

    async def _consume_messages_impl(self):
        get_nowait = self._message_queue.get_nowait
        is_empty = self._message_queue.empty
        while self.loop.is_running():
            # log.debug('{} queued message(s)', self._message_queue.qsize())
            message = await self._message_queue.get()
            self._on_message(message)
            while not is_empty:
                message = get_nowait()
                self._on_message(message)
            update = self._inst_handler.make_update()
            if update:
                self._publish_update(update)

    async def _poll_endpoint(self, endpoint):
        try:
            async with websockets.connect(endpoint, loop=self.loop) as sock:
                try:
                    await self._send_subscribe(sock)
                    while self.loop.is_running():
                        data = await sock.recv()
                        self._message_queue.put_nowait(json.loads(data))
                except asyncio.CancelledError:
                    log.warn('Canceled poll_endpoint')
        except websockets.exceptions.InvalidState:
            log.exception()
        except:
            log.exception()

    async def _send_subscribe(self, sock):
        message = json.dumps(
                {'type': 'subscribe', 'product_id': self._instrument})
        log.info('Subscribing: {}', message)
        await sock.send(message)

    def _check_sequence(self, message):
        received = int(message['sequence'])
        if received <= self._in_sequence:
            return True

        expected = self._in_sequence + 1
        valid = (received == self._in_sequence + 1)
        self._in_sequence = received
        if valid:
            return True

        self._handle_gap(expected=expected, received=received)
        return False

    def _handle_gap(self, expected, received):
        if self._recovery_task:
            log.notice('Gap detected during recovery: ' +
                       'expected={}, received={}', expected, received)
            self._recovery_task.cancel()
        else:
            log.notice('Gap detected: expected={}, received={}',
                       expected, received)
        self._clear_queue()
        self._recovery_handler.drop_stored()
        self._recovery_task = asyncio.ensure_future(
                self._start_recovery(),
                loop=self.loop)

    async def _start_recovery(self):
        snapshot = await self._recovery_handler.fetch_snapshot(
                self._instrument)
        seq, book = snapshot
        log.info('Exiting recovery at {}', seq)
        self._inst_handler.recover(seq, book)
        self._recovery_handler.apply_messages(
                self._inst_handler.handle_message)
        self._recovery_task = None
