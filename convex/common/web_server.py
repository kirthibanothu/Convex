import aiohttp
import aiohttp.web
import json

from convex.strategy_utils.logger import log


class WebServer:
    def __init__(self, message_cb):
        self.cb = message_cb
        pass

    async def init(self, loop, ip, port, instrument):
        self._app = aiohttp.web.Application(loop=loop)
        self._app['sockets'] = set()
        self._app.router.add_get('/ws', self.socket_handler)
        self._handler = self._app.make_handler()

        self._srv = await loop.create_server(self._handler, ip, port)
        self._session = aiohttp.ClientSession()

        log.info('Running web server at {}:{}', ip, port)

    async def broadcast_msg(self, name, msg_type, msg):
        resp = {name: {'type': msg_type, 'msg': msg}}
        await self.send_str(json.dumps(resp))

    async def send_str(self, data):
        for ws in self._app['sockets']:
            await ws.send_str(data)

    async def socket_handler(self, request):
        print("{}".format(request))
        ws = aiohttp.web.WebSocketResponse()
        ok, protocol = ws.can_prepare(request)
        if not ok:
            return aiohttp.web.Response(text='Somthing went wrong')

        await ws.prepare(request)

        request.app['sockets'].add(ws)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        req = json.loads(msg.data)
                        if 'admin' in req:
                            await self.cb(req)
                        elif 'config' in req:
                            log.info('Recieved new configuration: {}', req)
                            await self.cb(req)
                    except Exception as e:
                        log.exception('Unexpected Error: {}', e)
                        await ws.close()
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.info('Conn closed w/ exception: {}', ws.exception())
                    await ws.close()
        finally:
            request.app['sockets'].remove(ws)

        return ws
