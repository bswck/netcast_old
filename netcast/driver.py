from __future__ import annotations  # Python 3.8

import contextlib
import functools
import inspect
import sys
import typing
from typing import ClassVar, Type, Any

from netcast import common
from netcast.exceptions import NetcastError
from netcast.serializer import Serializer, SettingsT, Interface
from netcast.tools.collections import IDLookupDictionary

if typing.TYPE_CHECKING:
    from netcast.common import ModelSerializer
    from netcast.model import Model  # noqa: F401


__all__ = (
    "Driver",
    "DriverMeta",
    "driver_serializer",
    "driver_interface",
    "get_driver",
)

IMPLEMENTS_FIELD = "implements"
common_paths = ["netcast.drivers.%(driver_name)s"]


class DriverMeta(type):
    _memo: IDLookupDictionary[Model, Serializer]
    _map: dict[Type[Serializer], Type[Serializer]]

    default_model_serializer = None

    # Note: singledispatchmethod's __get__ doesn't return itself,
    #  but a function or method object instead - to provide the public API,
    #  it sets `register` attribute on it.
    init_model_serializer: functools.singledispatchmethod

    def _init_model_serializer(
        cls,
        origin: ModelSerializer,
        /,
        *,
        serializer: ModelSerializer,
        components: tuple[Any, ...] = (),
        settings: SettingsT = None,
    ) -> ModelSerializer:
        if settings is None:
            settings = {}
        settings = {**origin.settings, **settings}
        return serializer(*components, **settings)

    def lookup_model_serializer(cls, model: Model, /, **settings) -> Serializer:
        components = model.choose_components(**settings).values()
        model_serializer = getattr(model, "serializer", None)
        if model_serializer is None:
            model_serializer = cls.default_model_serializer
            origin = origin_type = getattr(model_serializer, IMPLEMENTS_FIELD, model_serializer)
            if not isinstance(origin, type):
                origin_type = type(origin)
        else:
            origin = origin_type = model_serializer
            if not isinstance(origin, type):
                origin_type = type(origin)
            model_serializer = cls.lookup_type(origin_type)
            if model_serializer is NotImplemented:
                raise NotImplementedError(
                    f"no implementation found for the {origin_type.__name__} serializer"
                )

        if isinstance(origin, type):
            origin = object.__new__(origin_type)
            object.__setattr__(origin, "settings", {})

        serializer = cls.init_model_serializer(
            origin,
            serializer=model_serializer,
            components=components,
            settings=settings,
        )
        return serializer

    def lookup_type(cls, serializer_type: type[Serializer]):
        try:
            return cls._map[serializer_type]
        except KeyError:
            return NotImplemented

    def __getattr__(cls, item):
        alias = getattr(common, item, None)
        if alias is None or (isinstance(alias, type) and not issubclass(alias, Serializer)):
            raise AttributeError(item)
        return object.__getattribute__(cls, alias.__name__)

    def __call__(
        self, model: Model | None = None, return_serializer: bool = True, **settings
    ) -> ModelSerializer:
        if return_serializer:
            if model is None:
                raise ValueError("`Model` type or instance expected")
            if isinstance(model, type):
                model = model()
            return model.impl(self, settings)
        return super().__call__()


class Driver(metaclass=DriverMeta):
    registry: dict[str, Type[Driver]] = {}
    _map: ClassVar[dict[Type[Serializer], Type[Serializer]]]
    DEBUG: ClassVar[bool]

    def __init_subclass__(cls, driver_name: str | None = None, config: bool = False):
        if config:
            return

        if driver_name is None:
            driver_name = cls._conjure_driver_name(stack_level=2)

        if driver_name in Driver.registry:
            raise ValueError(f"{driver_name!r} driver has already been implemented")

        cls.name = driver_name
        cls._map = {}
        cls._memo = IDLookupDictionary()
        cls.init_model_serializer = functools.singledispatchmethod(
            cls._init_model_serializer
        )

        for _, member in inspect.getmembers(cls, _check_impl):
            cls.impl(member)

        cls.DEBUG = __debug__
        Driver.registry[driver_name] = cls

    @staticmethod
    def _conjure_driver_name(stack_level: int = 1) -> str:
        f_globals = inspect.stack()[stack_level][0].f_globals
        driver_name = f_globals.get("DRIVER_NAME", f_globals.get("__name__"))
        if driver_name is None:
            raise ValueError("driver name is required")
        return sys.intern(driver_name)

    @classmethod
    def impl(cls, impl_counterpart: type[Interface]) -> type:
        link_to = getattr(impl_counterpart, IMPLEMENTS_FIELD, impl_counterpart.__base__)
        cls._map[link_to] = impl_counterpart
        name = impl_counterpart.__name__
        if name not in cls.__dict__:
            setattr(cls, name, impl_counterpart)
        return impl_counterpart

    @classmethod
    def initializes(cls, *types: type[Serializer]):
        def _register(init):
            for serializer_type in types:
                cls.init_model_serializer.register(serializer_type, init)
            return init

        return _register


def _check_impl(member: Any) -> bool:
    return isinstance(member, type) and issubclass(member, Serializer)


def get_driver(name: str, load: bool = True) -> DriverMeta | None:
    driver = Driver.registry.get(name)
    if driver is None and load:
        with contextlib.suppress(ValueError):
            load_driver(name)
        driver = Driver.registry.get(name)
    return driver


def driver_serializer(
    interface_class: type,
    serializer_class: type | None = None,
    origin: type | None = None,
):
    if serializer_class is None:
        raise NetcastError("no serializer has been set on this adapter")
    impl = type(
        serializer_class.__name__,
        (serializer_class, interface_class),
        {IMPLEMENTS_FIELD: (serializer_class if origin is None else origin)},
    )
    return impl


def driver_interface(
    interface_class: type[Interface],
    origin: type | None = None,
    default: type | None = None,
):
    if origin is None:
        origin = getattr(interface_class, IMPLEMENTS_FIELD, None)

    return lambda serializer_class=default: driver_serializer(
        interface_class, serializer_class, origin=origin
    )


def load_driver(driver_name: str, paths: list[str] | None = None):
    import importlib

    if paths is None:
        paths = common_paths
    else:
        paths = [*common_paths, *paths]

    for path in paths:
        try:
            return importlib.import_module(path % dict(driver_name=driver_name))
        except ImportError:
            pass

    raise ValueError(f"could not import driver named {driver_name!r}")
