import sys

from netcast.driver import Driver
from netcast.tools.arrangements import Arrangement


class Engine(Arrangement):
    def __init__(self, descent=None):
        super().__init__(descent)
        self.data = {}
        self.drivers = Driver.__drivers_registry__

    def get_driver(self, name) -> Driver:
        name = sys.intern(name)
        return self.drivers.get(name)


__global_engine = Engine()


def get_global_engine():
    return __global_engine
