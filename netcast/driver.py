import functools
import inspect
import sys
from typing import ClassVar, Type

from netcast import serializers
from netcast.exceptions import NetcastError
from netcast.serializer import Serializer


class DriverMeta(type):
    def __getattr__(self, item):
        alias = getattr(serializers, item, None)
        if (
            alias is None
            or not issubclass(alias, Serializer)
        ):
            raise AttributeError(item)
        return object.__getattribute__(self, alias.__name__)

    @functools.singledispatchmethod
    def get_model_serializer(cls, model_serializer, /, components=(), settings=None):
        if settings is None:
            settings = {}
        if model_serializer is None:
            model_serializer = cls.default_model_serializer
        return model_serializer(*components, **settings)

    def lookup(cls, serializer_type):
        try:
            return cls._lookup_dict[serializer_type]
        except KeyError:
            return NotImplemented


class Driver(metaclass=DriverMeta):
    __drivers_registry__ = {}
    _lookup_dict: ClassVar[dict[Type[Serializer], Type[Serializer]]]

    default_model_serializer = None

    @staticmethod
    def _conjure_driver_name(stack_level=1):
        f_globals = inspect.stack()[stack_level][0].f_globals
        driver_name = f_globals.get("DRIVER_NAME", f_globals.get("__name__"))
        if driver_name is None:
            raise ValueError("driver name is required")
        return sys.intern(driver_name)

    def __init_subclass__(cls, driver_name=None, config=False):
        if config:
            return

        if driver_name is None:
            driver_name = cls._conjure_driver_name(stack_level=2)

        if driver_name in Driver.__drivers_registry__:
            raise ValueError(f"{driver_name!r} driver has already been implemented")

        cls.__drivers_registry__[driver_name] = cls
        cls.name = driver_name
        cls._lookup_dict = {}

        for name, member in inspect.getmembers(cls, _is_impl):
            link_to = getattr(member, "__netcast_origin__", member.__base__)
            cls._lookup_dict[link_to] = member

    def __getattr__(self, item):
        return getattr(self.state, item)

    def __getitem__(self, item):
        return self.state[item]


def _is_impl(member):
    return isinstance(member, type) and issubclass(member, Serializer)


def serializer(
    implementation,
    serializer_class=None,
    origin=None
):
    if serializer_class is None:
        raise NetcastError("no serializer has been set on this adapter")
    impl = type(
        serializer_class.__name__,
        (serializer_class, implementation),
        {"__netcast_origin__": serializer_class if origin is None else origin}
    )
    return impl


def mixin(implementation, origin=None):
    return functools.partial(serializer, implementation, origin=origin)

