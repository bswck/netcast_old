import sys

from netcast.driver import Driver
from netcast.tools import Arrangement


class Engine(Arrangement):
    def __init__(self, descent=None):
        super().__init__(descent)
        self.data = {}
        self.drivers = Driver.__drivers_registry__

    def get_driver(self, name):
        name = sys.intern(name)
        return self.drivers.get(name)
