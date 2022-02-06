import functools
import inspect
import sys

from netcast import serializers
from netcast.serializer import Serializer
from netcast.plugin import Plugin
from netcast.state import State
from netcast.tools.collections import AttributeDict


class DriverMeta(type):
    def __getattr__(self, item):
        alias = getattr(serializers, item, None)
        if alias is None or not issubclass(alias, Serializer) or item == alias.__name__:
            raise AttributeError(item)
        return object.__getattribute__(self, alias.__name__)


class Driver(metaclass=DriverMeta):
    __drivers_registry__ = {}

    @staticmethod
    def _inspect_driver_name(stack_level=1):
        f_globals = inspect.stack()[stack_level][0].f_globals
        driver_name = f_globals.get("__driver_name__", f_globals.get("__name__"))
        if driver_name is None:
            raise ValueError("driver name is required")
        return sys.intern(driver_name)

    def __init_subclass__(cls, driver_name=None, config=False):
        if config:
            return
        if driver_name is None:
            driver_name = cls._inspect_driver_name(stack_level=2)
        if driver_name in Driver.__drivers_registry__:
            raise ValueError(f"{driver_name!r} driver has already been implemented")
        cls.__drivers_registry__[driver_name] = cls
        cls.name = driver_name

    def __new__(cls, model, engine=None):
        return State(model=model, driver=cls, engine=engine)


def adapted_serializer(serializer_class, adapter, stack_level=1):
    module = inspect.stack()[stack_level][0].f_globals["__name__"]
    return type(
        serializer_class.__name__, (serializer_class, adapter), {"__module__": module}
    )


def serializer_factory(adapter):
    return functools.partial(adapted_serializer, adapter=adapter, stack_level=2)


class Adapter(Plugin):
    _impls = {}
    cfg: AttributeDict  # as in the Serializer

    @property
    def impl(self):
        return self.cfg.impl
