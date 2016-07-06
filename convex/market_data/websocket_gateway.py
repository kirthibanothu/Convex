import asyncio

import websockets

from market_data.gateway import Gateway


class WebocketGateway(Gateway):
    def __init__(self, endpoints=None):
        self._subscribed_cond = asyncio.Condition()
        self._endpoints = {}  # Endpoint -> socket
        if endpoints:
            for e in endpoints:
                self._connect_endpoint(e)

    async def launch(self):
        """Start polling endpoints."""
        while True:
            await self._subscribed_cond.wait_for(self.has_endpoints)
            while self.has_endpoints():
                await self._listen()

    async def _listen(self):
        """Poll all endpoints."""
        recv_ep = self._recv_endpoint
        recvs = [recv_ep(e, s) for e, s in self._endpoints]
        await asyncio.wait(recvs, return_when=asyncio.FIRST_COMPLETED)

    def has_endpoints(self):
        return bool(self._endpoints)

    def _subscribe(self, instrument):
        for ep in self._subscribe_endpoints(instrument):
            self._connect_endpoint(ep)

    def _connect_endpoint(self, endpoint):
        if endpoint not in self._endpoints:
            self._endpoints[endpoint] = websockets.connect(endpoint)

    def _subscribe_endpoints(self, instrument):
        """Return endpoints for instrument."""
        raise NotImplementedError()

    def _parse_message(self, endpoint, message):
        """Parse update from message.

        Returns:
            market_data.Update: Market data update parsed from message.
        """
        raise NotImplementedError()

    async def _recv_endpoint(self, endpoint, socket):
        message = await socket.recv()
        await self._on_message(endpoint, message)

    async def _on_message(self, endpoint, message):
        update = self._parse_message(endpoint, message)
        await self._publish_update(update)
