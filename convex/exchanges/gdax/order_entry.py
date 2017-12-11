import ujson

import asyncio
import base64
import hmac
import hashlib
import time

import aiohttp
import logbook

from ..exchange_id import ExchangeID

from ...common import Side, make_qty

from ...order_entry.exceptions import SubmitNack, ReviseNack, CancelNack
from ...order_entry import gateway
from ...order_entry.order import Order
from ...order_entry.audit_log import AuditLog

log = logbook.Logger('GDAX')
audit = AuditLog(ExchangeID.GDAX)


class OrderEntryGateway(gateway.Gateway):
    """GDAX Order Entry Gateway"""
    API_URL = 'https://api.gdax.com'
    SANDBOX_URL = 'https://api-public.sandbox.gdax.com'

    def __init__(self,
                 api_url,
                 api_key,
                 secret_key,
                 passphrase,
                 loop):
        gateway.Gateway.__init__(self, loop)

        self._session = aiohttp.ClientSession(loop=loop)
        self._url = api_url
        self._api_key = api_key
        self._secret_key = secret_key
        self._passphrase = passphrase
        self._request_seq = 0  # Correlate request and response in audit log

        self._balances = {}  # Currency -> amount
        self._balance_task = None
        self._close_session = False
        self._ready_evt = asyncio.Event()

    async def launch(self):
        self._update_balances()
        self._ready_evt.set()

    def shutdown(self):
        self._close_session = True
        cancel_f = gateway.Gateway.cancel_all(self)
        asyncio.ensure_future(cancel_f, loop=self.loop)

    async def wait_ready(self):
        if self._ready_evt:
            await self._ready_evt.wait()
            self._ready_evt = None

    @property
    def exchange_id(self):
        return ExchangeID.GDAX

    async def get_balance(self, currency):
        if self._balance_task:
            self._balance_task.cancel()
            self._balance_task = None
        await self._fetch_balances()
        return self._balances.get(currency, 0)

    async def send_order(self, session, side, price, qty, ioc, post_only):
        req = {
            'product_id': '{i.base}-{i.quote}'.format(i=session.instrument),
            'side': 'sell' if side == Side.SELL else 'buy',
            'price': price,
            'size': qty,
        }

        if ioc:
            req['time_in_force'] = 'IOC'
        elif post_only:
            req['post_only'] = True

        log.info('Submitting order: {}', req)
        res = await self._post('/orders', req)
        try:
            order_id = res['id']
            status = res['status']
            if (status == 'rejected'):
                message = res.get('reject_reason')
                raise SubmitNack(message)
        except KeyError:
            message = res.get('message') or str(res)
            raise SubmitNack(message)
        else:
            self._update_balances()
            filled_qty = make_qty(res.get('filled_size', 0))
            remaining_qty = 0 if ioc else (qty - filled_qty)
            return Order(session=session,
                         order_id=order_id,
                         side=side,
                         price=price,
                         original_qty=qty,
                         remaining_qty=remaining_qty,
                         filled_qty=filled_qty)

    async def send_revise(self, order, price, qty):
        raise ReviseNack(order, 'Not supported')

    async def send_cancel(self, order):
        ENDPOINT_FMT = '/orders/{}'
        endpoint = ENDPOINT_FMT.format(order.order_id)
        res = await self._delete(endpoint)

        if isinstance(res, list):
            self._update_balances()
            for order_id in res:
                log.info('Cancelled: order={}', order)
        else:
            raise CancelNack(order, res['message'])

    async def send_cancel_all(self):
        res = await self._delete('/orders')
        if self._close_session:
            await self._session.close()

        if isinstance(res, list):
            if not self._close_session:
                self._update_balances()
            for order_id in res:
                log.info('Cancelled order: order_id={}', order_id)
        else:
            raise CancelNack(None, res['message'])

    async def exch_orders(self):
        return await self._get('/orders')

    async def get_fill(self, order_id):
        return await self._get('/fills?order_id={}'.format(order_id))

    async def get_fills(self):
        fills = await self._get('/fills')
        return fills

    def _update_balances(self):
        self._balances = None
        if self._balance_task:
            self._balance_task.cancel()
        self._balance_task = asyncio.ensure_future(self._fetch_balances(),
                                                   loop=self.loop)

    async def _fetch_balances(self):
        accounts = await self._get('/accounts')
        self._balances = {
            a['currency']: {
                'available': make_qty(a['available']),
                'hold': make_qty(a['hold'])
            } for a in accounts
        }

        log.debug('Updated balances: {}',
                  ', '.join(map('{0[0]}={0[1]}'.format,
                            self._balances.items())))
        if self._balance_task:
            self._balance_task = None

    def _next_request_sequence(self):
        """Increment request sequence."""
        self._request_seq += 1
        return self._request_seq

    async def _get(self, endpoint):
        """Send GET request."""
        seq = self._next_request_sequence()

        audit.outgoing('[{}] GET {} {}', seq, self._url, endpoint)
        headers = self._build_headers(endpoint, method='GET')
        req_path = self._url + endpoint
        async with self._session.get(req_path, headers=headers) as res:
            message = await res.json()
            audit.incoming('[{}] {}', seq, message)
            return message

    async def _post(self, endpoint, request):
        """Send POST request."""
        seq = self._next_request_sequence()
        data = ujson.dumps(request)
        audit.outgoing('[{}] POST {} {} {}', seq, self._url, endpoint, data)
        headers = self._build_headers(endpoint, method='POST', data=data)
        req_path = self._url + endpoint
        async with self._session.post(req_path,
                                      data=data,
                                      headers=headers) as res:
            message = await res.json()
            audit.incoming('[{}] {}', seq, message)
            return message

    async def _delete(self, endpoint):
        """Send DELETE request."""
        seq = self._next_request_sequence()

        audit.outgoing('[{}] DELETE {} {}', seq, self._url, endpoint)
        headers = self._build_headers(endpoint, method='DELETE')
        req_path = self._url + endpoint
        async with self._session.delete(req_path, headers=headers) as res:
            message = await res.json()
            audit.incoming('[{}] {}', seq, message)
            return message

    def _build_headers(self, endpoint, method='GET', data=None):
        """Build headers for request."""
        timestamp = str(time.time())
        message = timestamp + method.upper() + endpoint + (data or '')
        message = message.encode('utf-8')
        hmac_key = base64.b64decode(self._secret_key)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')
        return {
            'Content-Type': 'application/json',
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self._api_key,
            'CB-ACCESS-PASSPHRASE': self._passphrase
        }
