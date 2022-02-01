import sys

from netcast import Arrangement
from netcast.driver import Driver


class Engine(Arrangement):
    def __init__(self, descent=None, key=None):
        super().__init__(descent)
        self.data = {}
        self.drivers = Driver.__drivers_registry__

    def get_driver(self, name):
        name = sys.intern(name)
        return self.drivers.get(name)
