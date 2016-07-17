import asyncio
import signal

import logbook
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

log = logbook.Logger('APP')


class AsyncApp:
    LOG_FORMAT = \
        '{record.time:%Y-%m-%d %H:%M:%S.%f} - ' + \
        '{record.module} - ' + \
        '{record.level_name} - ' + \
        '{record.message}'

    def __init__(self, name, loop=None):
        self._name = name
        self._log_handler = logbook.TimedRotatingFileHandler(
                name + '.log',
                format_string=AsyncApp.LOG_FORMAT)
        self._loop = loop if loop else asyncio.get_event_loop()
        self._loop.add_signal_handler(signal.SIGINT, self._on_sigint)

    @property
    def loop(self):
        return self._loop

    def run_loop(self, *coros):
        with self._log_handler.applicationbound():
            log.info('Running AsyncApp, name={}', self._name)
            tasks = asyncio.gather(*coros)
            try:
                log.info('Running event loop with {} task(s)', len(coros))
                asyncio.ensure_future(tasks, loop=self._loop)
                self._loop.run_forever()
            except asyncio.CancelledError:
                log.notice('Tasks have been canceled')
            except:
                log.exception()
            finally:
                self._stop_loop()

    def _stop_loop(self):
        if self._loop.is_running():
            log.notice('Stopping event loop')
            self._loop.stop()
        else:
            log.notice('Event loop already stopped')

    def _cancel_all(self):
        log.notice('Cancelling tasks')
        task_count = 0
        for task in asyncio.Task.all_tasks(loop=self._loop):
            task_count += 1
            task.cancel()
        log.notice('Cancelled {} task(s)', task_count)

    def _on_sigint(self):
        log.notice('Caught {sig.name}:{sig.value}', sig=signal.SIGINT)
        self._stop_loop()
        self._cancel_all()
