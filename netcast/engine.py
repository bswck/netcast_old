from __future__ import annotations  # Python 3.8

import sys
import typing

from netcast.tools.arrangements import Arrangement

if typing.TYPE_CHECKING:
    from netcast.driver import Driver

__all__ = (
    "Engine",
    "get_global_engine"
)


class Engine(Arrangement):
    def __init__(self, descent=None):
        super().__init__(descent)
        from netcast.driver import Driver

        self.data = {}
        self.drivers = Driver.__drivers_registry__

    def get_driver(self, name) -> Driver:
        name = sys.intern(name)
        return self.drivers.get(name)


__global_engine = None


def get_global_engine():
    global __global_engine
    if __global_engine is None:
        __global_engine = Engine()
    return __global_engine
