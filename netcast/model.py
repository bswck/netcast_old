from __future__ import annotations  # Python 3.8

import collections.abc
import contextlib
import functools
import inspect
from typing import Any, cast, ClassVar, Type, TypeVar, Union

from netcast.constants import MISSING, GREATEST
from netcast.driver import DriverMeta, Driver, load_driver
from netcast.serializer import Interface, SettingsT, Serializer
from netcast.stack import Stack, VersionAwareStack
from netcast.tools import strings
from netcast.tools.collections import IDLookupDictionary, classproperty


__all__ = (
    "check_component",
    "ComponentArgT",
    "ComponentT",
    "create_model",
    "Field",
    "FieldAlias",
    "Model",
)

FIELD_NAME_ESCAPE = "f__"
REPEATED_NAME_TEMPLATE = "%(name)s[%(size)d]"
REPEATED_MEMBER_NAME_TEMPLATE = "%(name)s_%(index)d"


def escape(field_name: str) -> str:
    return FIELD_NAME_ESCAPE + field_name


def unescape(field_name: str) -> str:
    return strings.remove_prefix(field_name, FIELD_NAME_ESCAPE)


class ModelProperty:
    component: ComponentT


class Field(ModelProperty):
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

    def __get__(self, instance: Model | None, owner: type[Model] | None) -> Any:
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


class FieldAlias(ModelProperty):
    def __init__(self, ancestor: Field):
        self.ancestor = ancestor

    @property
    def component(self) -> ComponentT:
        return self.ancestor.component

    def __get__(self, instance: Model | None, owner: type[Model] | None) -> Any:
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
    name: str
    _field_class = Field
    _field_alias_class = FieldAlias
    _repeated_name_template = None
    _repeated_member_name_template = None

    def __init__(
        self,
        defaults: dict[str, Any] | None = None,
        empty: Any = None,
        /,
        **settings,
    ):
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

    def _choose_descriptors(self, settings: SettingsT) -> dict[Any, Field]:
        namespace = set(self.choose_components(**settings))
        descriptors = {
            name: desc for name, desc in self._descriptors.items() if name in namespace
        }
        return descriptors

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

    def with_(self, **values):
        return self.set_state(values)

    def impl(
        self, driver: DriverArgT = None, settings: SettingsT = None, final: bool = False
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
        source = serializer.ensure_load_type(self.get_state(**settings))
        return serializer.dump(source, settings)

    def load(
        self, driver: DriverArgT = None, dump: Any = MISSING, /, **settings
    ) -> Model:
        return self.load_state(self.load_externally(driver, dump, **settings))

    def load_externally(
        self, driver: DriverArgT = None, dump: Any = MISSING, /, **settings
    ):
        if dump is MISSING:
            raise ValueError("the source to load from is a required argument")
        serializer = self.impl(driver, settings)
        source = serializer.ensure_dump_type(dump)
        return serializer.load(source, settings)

    def load_state(self, load: Any):
        state = self.read_state(load)
        self.set_state(state)
        return self

    # noinspection PyPropertyDefinition
    @classproperty
    def priority(cls):
        return cls.settings.setdefault("priority", 0)

    @functools.singledispatchmethod
    def read_state(self, load: Any) -> dict | tuple[tuple[str, Any], ...]:
        raise TypeError(f"unsupported state type: {type(load).__name__}")

    @read_state.register
    def read_sequence_state(self, load: collections.abc.Sequence) -> "dict[str, Any]":
        return dict(zip(self._descriptors, load))

    @read_state.register
    def read_mapping_state(self, load: collections.abc.Mapping) -> dict:
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

    def __class_getitem__(cls, repeat):
        return repeated(cls, repeat, name=cls.name)

    def __getitem__(self, key: Any):
        return self._descriptors[key].__get__(self, None)

    def __setattr__(self, key: str, value: Any):
        if key in self._descriptors:
            self._descriptors[key].__set__(self, value)
            return
        # TODO: find a better way to do it
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
        cls._descriptors = final = collections.OrderedDict()
        descriptors = {}
        seen_descriptors = IDLookupDictionary()

        for idx, (attribute, component) in enumerate(
            inspect.getmembers(cls, check_component), start=1
        ):
            seen = seen_descriptors.get(component)
            attribute_unescaped = unescape(attribute)

            if seen is None:
                if not (isinstance(component, type) and not issubclass(component, Model)):
                    if component.priority == 0:
                        component.settings["priority"] = idx
                dep = stack.add(component, name=attribute_unescaped, settings=settings)
                field = dep
                if not isinstance(field, Field):
                    field = cls._field_class(dep)
                name = dep.name
                if name == attribute_unescaped:
                    name = attribute
            else:
                name = attribute_unescaped
                field = cls._field_alias_class(seen)

            setattr(cls, name, field)

            descriptors[name] = field
            seen_descriptors[component] = field

        final.update(sorted(descriptors.items(), key=lambda kv: kv[1].priority))
        descriptors.clear()
        seen_descriptors.clear()

    @classmethod
    def _load_stack(cls, stack, settings: SettingsT):
        components = stack.choose_components(**settings)
        cls._descriptors = descriptors = collections.OrderedDict()

        for idx, (name, component) in enumerate(components.items(), start=1):
            component.settings.setdefault("priority", idx)
            descriptor = descriptors[name] = cls._field_class(component)
            while isinstance(getattr(cls, name, None), ModelProperty):
                name = escape(name)
            setattr(cls, name, descriptor)

    @classmethod
    def _normalize_settings(cls, settings: SettingsT):
        normalized = {}
        for key, value in settings.items():
            normalized[unescape(key)] = value
        return normalized

    def __init_subclass__(
        cls,
        stack: Stack | None = None,
        name: str | None = None,
        build_stack: bool | None = None,
        stack_class: type[Stack] = VersionAwareStack,
        serializer: type[Serializer] | None = None,
        include: tuple[str, ...] | None = None,
        **settings: Any,
    ):
        if build_stack is None:
            build_stack = stack is None

        if stack is None:
            base = cls.__base__
            stack = stack_class()
            if issubclass(base, Model) and base != Model:
                include_from = base.stack.all()
                if include is None:
                    for component in include_from:
                        stack.push(component)
                else:
                    for name in include:
                        matched = tuple(
                            filter(lambda comp: comp.name == name, include_from)
                        )
                        if len(matched) > 1:
                            raise ValueError(f"multiple components match name {name!r}")
                        if len(matched) == 0:
                            raise ValueError(f"no component matches name {name!r}")
                        stack.push(*matched)

        settings = cls._normalize_settings(settings)

        if build_stack:
            cls._build_stack(stack, settings)
        else:
            cls._load_stack(stack, settings)

        if serializer is not None:
            cls.serializer = serializer

        cls.stack = stack
        cls.settings = settings

        if name is None:
            name = cls.__name__.casefold()
        cls.name = name


ComponentT = TypeVar("ComponentT", Serializer, Model)
ComponentArgT = Union[ComponentT, Type[ComponentT]]


def check_component(obj: Any, acknowledge_type: bool = True) -> bool:
    is_instance = isinstance(obj, (Serializer, Model))
    is_type = (
        acknowledge_type
        and isinstance(obj, type)
        and issubclass(obj, (Serializer, Model))
    )
    return is_instance or is_type


def create_model(
    *components: ComponentArgT,
    stack: Stack | None = None,
    name: str | None = None,
    model_class: type[Model] = Model,
    model_metaclass: type[Type] = type,
    stack_class: type[Stack] = VersionAwareStack,
    serializer: type[Serializer] | None = None,
    **settings,
) -> Type[Model]:
    if stack is None:
        stack = stack_class()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    model = model_metaclass(
        name,
        (model_class,),
        {},
        name=name,
        stack=stack,
        serializer=serializer,
        **settings,
    )
    return cast(Type[Model], model)


def repeated(
    cls,
    repeat,
    name=None,
    name_template=None,
    member_name_template=None,
    factory=create_model,
) -> Type[Model]:
    if repeat < 1:
        raise ValueError("dimension size must be at least 1")
    if name_template is None:
        name_template = REPEATED_NAME_TEMPLATE
    if member_name_template is None:
        member_name_template = REPEATED_MEMBER_NAME_TEMPLATE
    if name is None:
        name = cls.__name__
    fmt = {"name": name, "size": repeat}
    components = (cls(name=member_name_template % {**fmt, "index": i + 1} for i in range(repeat)))
    return factory(*components, name=name_template % fmt)
