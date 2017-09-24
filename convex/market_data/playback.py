import json
import collections
import itertools as it

import msgpack


class StopPlayback(StopIteration):
    """Raised when playback of a file is finished."""


class Playback:
    def __init__(self, path_or_buff, fmt=None, *, chunksize=256):
        if not isinstance(path_or_buff, str):
            if fmt is None:
                raise ValueError('Stream input must specify format')
            else:
                fmt = self._deduce_format(fmt)
            self._file = path_or_buff
            self._close_file = lambda: None  # Don't close others' files
        else:
            self._file = None
            self._close_file = lambda: self._file.close()
            if fmt is None:
                fmt = self._deduce_format(path_or_buff)

        if fmt == 'json':
            self._read_next = self._read_json
            if self._file is None:
                self._file = open(path_or_buff)
        elif fmt == 'msgpack':
            self._read_next = self._read_msgpack
            if self._file is None:
                self._file = open(path_or_buff, 'rb')
            self._unpacker = msgpack.Unpacker(self._file, encoding='utf-8')
        else:
            raise ValueError('Unknown format \'{}\''.format(fmt))

        chunksize = int(chunksize) if chunksize and chunksize > 0 else None
        self._chunksize = chunksize
        self._updates = collections.deque(maxlen=chunksize)

    def next_update(self) -> dict:
        """Get next update."""
        if not self._updates and not self._read_next():
            self._read_next = Playback._read_finished
            self._close_file()
            raise StopPlayback()
        return self._updates.popleft()

    def __iter__(self):
        return self

    __next__ = next_update

    def _read_next(self):
        """Read next chunk of updates from file."""
        raise RuntimeError('Should be replaced by '
                           '_read_json or _read_msgpack')

    def _read_json(self):
        for line in it.islice(self._file, self._chunksize):
            update = json.loads(line)
            self._updates.append(update)
        return self._updates

    def _read_msgpack(self):
        for data in it.islice(self._unpacker, self._chunksize):
            self._updates.append(data)
        return self._updates

    @staticmethod
    def _read_finished():
        raise StopPlayback()

    @staticmethod
    def _deduce_format(filename : str) -> str:
        file_ext = filename.rsplit('.', maxsplit=1)[-1]
        if file_ext in ('json', 'js'):
            return 'json'
        elif file_ext in ('mp', 'msgpack'):
            return 'msgpack'
        else:
            raise ValueError('Cannot deduce format from '
                             '\'{}\''.format(filename))
