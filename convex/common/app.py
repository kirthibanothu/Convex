import asyncio
import signal

from logbook import TimedRotatingFileHandler


class AsyncApp:
    LOG_FORMAT = \
        '{record.time:%Y-%m-%d %H:%M:%S.%f} - ' + \
        '{record.module} - ' + \
        '{record.level_name} - ' + \
        '{record.message}'

    def __init__(self, name, loop=None):
        self._log_handler = TimedRotatingFileHandler(
                name + '.log',
                format_string=AsyncApp.LOG_FORMAT)
        self._loop = loop if loop else asyncio.get_event_loop()
        self._loop.add_signal_handler(signal.SIGINT, self._on_sigint)

    @property
    def loop(self):
        return self._loop

    def run_loop(self, *coros):
        with self._log_handler.applicationbound():
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
