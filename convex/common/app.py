import asyncio
import signal


class AsyncApp:
    def __init__(self, loop=None):
        self._loop = loop if loop else asyncio.get_event_loop()
        self._loop.add_signal_handler(signal.SIGINT, self._on_sigint)

    @property
    def loop(self):
        return self._loop

    def run_loop(self, *coros):
        tasks = asyncio.gather(*coros)
        try:
            self._loop.run_until_complete(tasks)
        except asyncio.CancelledError:
            print('Tasks have been canceled')
        finally:
            self._loop.stop()
            self._loop.close()

    def _on_sigint(self):
        for task in asyncio.Task.all_tasks(loop=self._loop):
            task.cancel()
