import pathlib

import orjson

from contentfilter.constants import Conf


class Database(list):
    def __init__(self, fpath: pathlib.Path):
        if fpath.exists():
            with open(fpath, "r") as fh:
                super().__init__(orjson.loads(fh.read()))
        else:
            super().__init__()
        self.fpath = fpath

    def _sync(self):
        """sync db to JSON on disk"""
        with open(self.fpath, "wb") as fh:
            fh.write(orjson.dumps(self))

    def add(self, item):
        if item not in self:
            self.append(item)

    def append(self, *args):
        super().append(*args)
        self._sync()

    def clear(self):
        super().clear()
        self._sync()

    def extend(self, *args):
        super().extend(*args)
        self._sync()

    def insert(self, *args):
        super().insert(*args)
        self._sync()

    def pop(self, *args):
        super().pop(*args)
        self._sync()

    def remove(self, *args):
        super().remove(*args)
        self._sync()

    def reverse(self, *args):
        super().reverse(*args)
        self._sync()

    def sort(self, *args):
        super().sort(*args)
        self._sync()


database = Database(Conf.database_path)
