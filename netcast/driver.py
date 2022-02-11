import functools
import inspect
import sys

from netcast import serializers
from netcast.plugin import Plugin
from netcast.exceptions import NetcastError
from netcast.serializer import Serializer
from netcast.state import State


class DriverMeta(type):
    def __getattr__(self, item):
        alias = getattr(serializers, item, None)
        if (
            alias is None
            or not issubclass(alias, Serializer)
        ):
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

    def __init__(self, model, engine=None):
        self.state = State(model=model, driver=type(self), engine=engine)

    def __getattr__(self, item):
        return getattr(self.state, item)

    def __getitem__(self, item):
        return self.state[item]


def _build_adapted_serializer(
        adapter,
        serializer_class=None,
        stack_level=1
):
    if serializer_class is None:
        raise NetcastError("no serializer has been set on this adapter")

    return type(
        serializer_class.__name__,
        (serializer_class, adapter),
        {"__module__": inspect.stack()[stack_level][0].f_globals["__name__"]}
    )


def serializer_factory(adapter):
    return functools.partial(_build_adapted_serializer, adapter, stack_level=2)


Adapter = type("Adapter", (Plugin,), {})
