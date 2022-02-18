from __future__ import annotations  # Python 3.8

import dataclasses
import sys
import threading


@dataclasses.dataclass(frozen=True)
class Symbol:
    """An initializer-dependent singleton. Used as a mark or a sentinel."""

    __cache = {}
    __name_default = "_"
    __mutex = threading.RLock()

    name: str = dataclasses.field(default=__name_default)

    def __post_init__(self):
        with self.__mutex:
            self.__cache[self.name] = self

    def __new__(cls, name=__name_default):
        name = sys.intern(name)
        if name in cls.__cache:
            return cls.__cache[name]
        return object.__new__(cls)

    def __repr__(self):
        return self.name
