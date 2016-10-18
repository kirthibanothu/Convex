try:
    import ujson as json
except ImportError:
    import json

import asyncio
import inspect
import collections
import itertools

import logbook
import websockets

log = logbook.Logger('Amp')


class ResponseConnection:
    """Connection used to respond directly to connection."""
    def __init__(self, conn):
        self._conn = conn

    @property
    def remote_address(self):
        return self._conn.remote_address

    async def reply(self, obj):
        """Send object that may be converted to JSON.

        This method is a coroutine.
        """
        message = json.dumps(obj)
        await self._conn.send(message)


class Server:
    TARGET_ID_GEN = itertools.count(1)

    def __init__(self, address='localhost', port=5678):
        self._cbs = set()
        self._target_cbs = collections.defaultdict(set)  # target -> callbacks
        self._addr = address, port
        self._conns = set()
        self._server = None
        self.listen(target="targets", cb=self._on_targets)

    async def run(self):
        """Run Amplify server.

        This method is a coroutine.
        """
        server = websockets.serve(self._on_conn, self._addr[0], self._addr[1])
        await server
        log.info('Amplify server started: {}:{}',
                 *self._addr)

    @property
    def local_address(self):
        return self._addr

    @staticmethod
    def next_target_id():
        """Generate unique target ID."""
        return str(next(Server.TARGET_ID_GEN))

    def targets(self):
        """Return target IDs with callbacks."""
        return self._target_cbs.keys()

    def listen(self, target, cb):
        """Register callback for message with target callback.

        Args:
            target (str): target ID
            cb: coroutine called as cb(message, conn)
        """
        self._target_cbs[target].add(cb)

    def listen_all(self, cb):
        """Register callback for messages without a target.

        Args:
            cb: coroutine called as cb(message, conn)
        """
        self._cbs.add(cb)

    async def broadcast(self, obj):
        """Send object that may be converted to JSON to all connected sessions.

        This method is a coroutine.
        """
        log.info('Broadcasting to {} connection(s): message={}',
                 len(self._conns), obj)
        if self._conns:
            message = json.dumps(obj)
            sends = [conn.send(message) for conn in self._conns]
            await asyncio.wait(sends)

    async def _on_conn(self, conn, path):
        log.info('Connection received: address={}:{}', *conn.remote_address)
        self._conns.add(conn)
        try:
            while True:
                message = await conn.recv()
                await self._on_message(message, conn)
        except websockets.exceptions.ConnectionClosed:
            log.notice('Connection closed: address={}:{}',
                       *conn.remote_address)
        except asyncio.CancelledError:
            log.notice('Cancelled with pending connection: address={}:{}',
                       *conn.remote_address)
        finally:
            self._conns.remove(conn)

    async def _on_message(self, message, conn):
        try:
            message = json.loads(message)
        except ValueError:
            log.error('Could not decode JSON: message=\'{}\', address={}',
                      message, conn.remote_address)
            return

        try:
            target = message['target']
        except KeyError:
            await Server._dispatch(self._cbs, message, conn)
        else:
            cbs = self._target_cbs.get(target)
            await Server._dispatch(cbs, message, conn)

    async def _on_targets(self, _, conn):
        res = {"targets": list(self.targets())}
        await conn.reply(res)

    @staticmethod
    async def _dispatch(cbs, message, conn):
        if not cbs:
            log.warn('No callbacks for dispatch: message={}', message)
            return

        res_conn = ResponseConnection(conn)
        log.info('Dispatching to {} callback(s): message={}',
                 len(cbs), message)
        dispatches = [Server._call(cb, message, res_conn) for cb in cbs]
        await asyncio.wait(dispatches)

    @staticmethod
    async def _call(cb, message, conn):
        try:
            res = cb(message, conn)
            if inspect.isawaitable(res):
                await res
        except:
            log.exception()
