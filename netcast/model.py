from __future__ import annotations  # Python 3.8

import collections.abc
import contextlib
import functools
import inspect
from typing import Any, ClassVar, Type, TypeVar, Union, cast

from netcast.constants import MISSING, GREATEST
from netcast.driver import DriverMeta, Driver, load_driver
from netcast.serializer import Interface, SettingsT, Serializer
from netcast.stack import Stack, VersionAwareStack


__all__ = (
    "check_component",
    "Rep",
    "ComponentArgumentT",
    "ComponentT",
    "create_model",
    "Model",
    "Proxy",
)

from netcast.tools import strings
from netcast.tools.collections import IDLookupDictionary

ESCAPE_PREFIX = "set__"


class RepT:
    component: ComponentT


class Rep(RepT):
    def __init__(self, component: ComponentT):
        self.component = component
        self.states = IDLookupDictionary()
        self.models = IDLookupDictionary()

    @functools.cached_property
    def refers_to_model(self):
        return isinstance(self.component, type) and issubclass(self.component, Model)

    def get_component(self, model: Model) -> Serializer | Model:
        if self.refers_to_model:
            component = self.models.get(model)
            if component is None:
                component = self.component()
                self.models[model] = component
        else:
            component = self.component
        return component

    def get_state(
        self, instance: Model, empty: Any = MISSING, settings: SettingsT = None
    ):
        if self.refers_to_model:
            if settings is None:
                settings = {}
            return self.get_component(instance).get_state(empty, **settings)
        state = self.states.setdefault(instance, empty)
        return empty if state is MISSING else state

    def __get__(self, instance: Model | None, owner: Type[Model] | None) -> Any:
        if instance is None:
            return self
        if self.refers_to_model:
            return self.get_component(instance)
        return self.get_state(instance)

    def __set__(self, instance: Model | None = None, state: Any = MISSING):
        if self.refers_to_model:
            model = self.get_component(instance)
            if state is MISSING:
                model.clear()
            else:
                model.set_state(state)
        else:
            self.states[instance] = state

    def __call__(self, state) -> Any:
        self.__set__(state=state)
        return state

    def __getattr__(self, attribute: str) -> Any:
        return getattr(self.component, attribute)


class Proxy(RepT):
    def __init__(self, ancestor: Rep):
        self.ancestor = ancestor

    @property
    def component(self) -> ComponentT:
        return self.ancestor.component

    def __get__(self, instance: Model | None, owner: Type[Model] | None) -> Any:
        if instance is None:
            return self
        return self.ancestor.__get__(instance, owner)

    def __set__(self, instance: Model | None = None, new_state: Any = MISSING):
        self.ancestor.__set__(instance, new_state)

    def __call__(self, state: Any) -> Any:
        return self.ancestor(state)

    def __getattr__(self, attribute: str) -> Any:
        return getattr(self.ancestor, attribute)


DriverArgT = Union[DriverMeta, Interface, str, type(None)]


@functools.total_ordering
class Model:
    stack: ClassVar[Stack]
    settings: ClassVar[dict[str, Any]]
    component_class = Rep
    proxy_class = Proxy
    name: str

    def __init__(
        self,
        defaults: dict[str, Any] | None = None,
        empty: Any = None,
        /,
        **settings,
    ):
        super().__init__()

        if empty is MISSING:
            raise ValueError("Model arg 2 must not be a netcast.MISSING constant")

        if defaults is None:
            defaults = {}

        default_driver = self.settings.pop("default_driver", None)
        propagate_driver = self.settings.pop("propagate_driver", True)
        settings = self._normalize_settings(settings)

        self._defaults = defaults
        self._empty = empty

        self._infer_states(settings)
        self._init_defaults()

        self.contained: bool = False

        if isinstance(default_driver, str):
            with contextlib.suppress(ValueError):
                load_driver(default_driver)
            try:
                default_driver = Driver.registry[default_driver]
            except KeyError:
                raise ValueError(
                    f"invalid driver name provided: {default_driver}"
                ) from None

        self.default_driver = default_driver
        self.propagate_driver = propagate_driver
        self.settings = {**self.settings, **settings}

    def _infer_states(self, settings: SettingsT):
        for key in settings.copy():
            if key in self._descriptors:
                self[key] = settings.pop(key)

    def _init_defaults(self):
        for key, value in self.default.items():
            if self[key] is MISSING:
                self[key] = value

    @property
    def default(self) -> Any:
        defaults = self._defaults.copy()
        for name, descriptor in self._descriptors.items():
            model = descriptor.get_component(self)
            default = model.default
            if default is not MISSING:
                defaults[name] = default
        return defaults

    @property
    def state(self) -> dict:
        return self.get_state(self._empty)  # we make it safe to avoid unsafe property

    @classmethod
    def configure(cls, **settings):
        cls.name = settings.pop("name", cls.name)
        cls.settings.update(settings)
        return cls

    def get_state(self, empty=MISSING, /, **settings: Any) -> dict:
        descriptors = self._choose_descriptors(settings)
        states = {}
        for name, descriptor in descriptors.items():
            state = descriptor.get_state(self, empty, settings)
            if state is MISSING:
                if empty is not MISSING:
                    state = empty
                else:
                    raise ValueError(
                        f"missing required {type(descriptor.component).__name__} "
                        f"value for serializer named {descriptor.component.name!r}"
                    )
            states[name] = state
        return states

    def choose_components(self, **settings: Any) -> dict[Any, ComponentT]:
        settings = {**settings, **self.settings}
        return self.stack.choose_components(settings)

    def _choose_descriptors(self, settings: SettingsT) -> dict[Any, Rep]:
        namespace = set(self.choose_components(**settings))
        descriptors = {
            name: desc for name, desc in self._descriptors.items() if name in namespace
        }
        return descriptors

    def with_(self, **values):
        return self.set_state(values)

    def impl(
            self,
            driver: DriverArgT = None,
            settings: SettingsT = None,
            final: bool = False
    ):
        if settings is None:
            settings = {}
        settings = {**settings, **self.settings}
        default_driver = self.default_driver
        if driver is None:
            driver = self.default_driver
            if driver is None:
                raise ValueError(f"neither driver nor default driver provided")
        elif isinstance(driver, str):
            driver_name = driver
            with contextlib.suppress(ValueError):
                load_driver(driver_name)
            driver = Driver.registry.get(driver_name, default_driver)
            if driver is None:
                raise ValueError(f"no driver named {driver_name!r} available")
        if isinstance(driver, DriverMeta):
            settings.update(name=self.name)
            serializer = driver.lookup_model_serializer(self, **settings)
        else:
            serializer = driver
            settings.update(name=self.name, default=self.default)
            serializer = serializer.get_dep(serializer, **settings)
        if final:
            return serializer.impl(driver, settings, final=final)
        return serializer

    def dump(self, driver: DriverArgT = None, /, **settings: Any) -> Any:
        serializer = self.impl(driver, settings)
        return serializer.dump(self.get_state(**settings), settings)

    def load(self, driver: DriverArgT = None, dump: Any = MISSING, /, **settings) -> Model:
        if dump is MISSING:
            raise ValueError("the source to load from is a required argument")
        serializer = self.impl(driver, settings)
        return self.load_state(serializer.load(dump, settings))

    def load_state(self, load: Any):
        state = self.parse_state(load)
        self.set_state(state)
        return self

    @functools.singledispatchmethod
    def parse_state(self, load: Any) -> dict | tuple[tuple[str, Any], ...]:
        raise TypeError(f"unsupported state type: {type(load).__name__}")

    @parse_state.register
    def parse_sequence(self, load: collections.abc.Sequence) -> "dict[str, Any]":
        return dict(zip(self._descriptors, load))

    @parse_state.register
    def parse_mapping(self, load: collections.abc.Mapping) -> dict:
        return dict(load)

    def set_state(self, state: dict):
        if callable(getattr(state, "items", None)):
            state = state.items()
        for item, value in state:
            try:
                self[item] = value
            except KeyError:
                pass
        return self

    def clear(self):
        return self.set_state(dict.fromkeys(self._descriptors, MISSING))

    @classmethod
    def clone(cls, name=None, settings=None):
        if name is None:
            name = cls.name
        old_settings = cls.settings.copy()
        if settings is None:
            settings = {}
        new_settings = {**old_settings, **settings}
        return create_model(stack=cls.stack, name=name, **new_settings)

    def __iter__(self):
        for name in self._descriptors:
            yield name, self[name]

    def __setitem__(self, key: Any, value: Any):
        self._descriptors[key].__set__(self, value)

    def __class_getitem__(cls, size):
        if size < 1:
            raise ValueError("dimension size must be at least 1")
        components = [cls.clone(name=f"{cls.name}_{i+1}") for i in range(size)]
        return create_model(*components, name=f"{cls.name}_x{size}")

    def __getitem__(self, key: Any):
        return self._descriptors[key].__get__(self, None)

    def __setattr__(self, key: str, value: Any):
        if key in self._descriptors:
            self._descriptors[key].__set__(self, value)
            return

        object.__setattr__(self, key, value)

    def __eq__(self, other: Model):
        if not isinstance(other, Model):
            return NotImplemented

        return self.get_state() == other.get_state()

    def __lt__(self, other: Model):
        if not isinstance(other, Model):
            return NotImplemented

        state = self.get_state()
        other_state = dict.fromkeys(self.get_state(), GREATEST)
        input_state = other.get_state()

        for key in state.keys() & input_state.keys():
            other_state[key] = input_state[key]

        return tuple(state.values()) < tuple(other_state.values())

    @classmethod
    def _build_stack(cls, stack, settings):
        cls._descriptors = descriptors = {}
        seen_descriptors = IDLookupDictionary()

        for attribute, component in inspect.getmembers(cls, check_component):
            seen = seen_descriptors.get(component)

            if seen is None:
                dep = stack.add(component, name=attribute, settings=settings)
                name = dep.name
                descriptor = dep
                if not isinstance(descriptor, Rep):
                    descriptor = cls.component_class(dep)

            else:
                name = attribute
                descriptor = cls.proxy_class(seen)

            setattr(cls, name, descriptor)

            descriptors[name] = descriptor
            seen_descriptors[component] = descriptor

        seen_descriptors.clear()

    @classmethod
    def _load_stack(cls, stack, settings: SettingsT):
        components = stack.choose_components(**settings)
        cls._descriptors = descriptors = {}

        for idx, (name, component) in enumerate(components.items()):
            descriptor = descriptors[name] = cls.component_class(component)
            setattr(cls, name, descriptor)

    @classmethod
    def _normalize_settings(cls, settings: SettingsT):
        normalized = {}
        for key, value in settings.items():
            normalized[strings.remove_prefix(key, ESCAPE_PREFIX)] = value
        return normalized

    def __init_subclass__(
        cls,
        stack: Stack = None,
        name: str | None = None,
        build_stack: bool | None = None,
        stack_class: Type[Stack] = VersionAwareStack,
        **settings: Any,
    ):
        if build_stack is None:
            build_stack = stack is None

        if stack is None:
            stack = stack_class()

        settings = cls._normalize_settings(settings)

        if build_stack:
            cls._build_stack(stack, settings)
        else:
            cls._load_stack(stack, settings)

        cls.stack = stack
        cls.settings = settings

        if name is None:
            name = cls.__name__.casefold()
        cls.name = name


ComponentT = TypeVar("ComponentT", Serializer, Model)
ComponentArgumentT = Union[ComponentT, Type[ComponentT]]


def check_component(obj: Any, acknowledge_type: bool = True) -> bool:
    is_instance = isinstance(obj, (Serializer, Model))
    is_type = (
        acknowledge_type
        and isinstance(obj, type)
        and issubclass(obj, (Serializer, Model))
    )
    return is_instance or is_type


def create_model(
    *components: ComponentArgumentT,
    stack: Stack | None = None,
    name: str | None = None,
    model_class: Type[Model] = Model,
    model_metaclass: Type[Type] = type,
    stack_class: Type[Stack] = VersionAwareStack,
    **settings,
) -> Type[Model]:
    if stack is None:
        stack = stack_class()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    model = model_metaclass(
        name, (model_class,), {}, name=name, stack=stack, **settings
    )
    return cast(Type[Model], model)
