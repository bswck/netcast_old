import inspect
import sys

from netcast.cast.plugin import Plugin, default
from netcast.toolkit.collections import AttributeDict


class Driver:
    _drivers = {}

    @staticmethod
    def _inspect_driver_name(stack_level=1):
        f_globals = inspect.stack()[stack_level][0].f_globals
        driver_name = f_globals.get('__driver_name__', f_globals.get('__name__'))
        if driver_name is None:
            raise ValueError('driver name is required')
        return sys.intern(driver_name)

    def __init_subclass__(cls, driver_name=None):
        if driver_name is None:
            driver_name = cls._inspect_driver_name(stack_level=2)
        if driver_name in Driver._drivers:
            raise ValueError(f'{driver_name!r} driver has already been implemented')
        Driver._drivers[driver_name] = cls


def serializer_impl(serializer_class, adapter):
    return type(serializer_class.__name__, (serializer_class, adapter), {})


class DriverSerializer(Plugin):
    _impls = {}
    cfg: AttributeDict  # as in the Serializer

    @default
    @property
    def impl(self):
        raise NotImplementedError
