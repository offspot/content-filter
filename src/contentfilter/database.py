import pathlib
from ast import TypeVar
from collections.abc import (
    Callable,
)

import orjson

from contentfilter.constants import Conf

_T = TypeVar("_T")


class Database(list):
    def __init__(self, fpath: pathlib.Path):
        if fpath.exists():
            super().__init__(orjson.loads(fpath.read_bytes()))
        else:
            super().__init__()
        self.fpath = fpath

    def _sync(self):
        """sync db to JSON on disk"""
        self.fpath.write_bytes(orjson.dumps(self))

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

    def sort(self, key: Callable, reverse: bool = False) -> None:  # type: ignore
        super().sort(key=key, reverse=reverse)
        self._sync()


database = Database(Conf.database_path)
