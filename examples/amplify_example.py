#!/usr/bin/env python3

from convex.common.app import AsyncApp

from convex import amplify


def main():
    app = AsyncApp(name='amplify_example')
    amp = amplify.Server(address='localhost', port=5678)
    app.add_run_callback(amp.run)

    async def echo(message, conn):
        await conn.reply(message)

    async def echo_broadcast(message, _):
        await amp.broadcast(message)

    amp.listen(target='echo', cb=echo)  # {"target": "echo", ...}
    amp.listen_all(echo_broadcast)
    app.run()

if __name__ == '__main__':
    main()
