from __future__ import annotations

import inspect
import threading
import typing

from netcast.engine import get_global_engine


if typing.TYPE_CHECKING:
    from netcast import Driver


class ComponentStack:
    def __init__(self):
        self._components = []
        self._lock = threading.RLock()

    @classmethod
    def transform_submodel(cls, submodel):
        return submodel

    @classmethod
    def transform_component(cls, component, settings=None):
        if settings is None:
            settings = {}
        return component.copy(**settings)

    def transform_item(self, component, *, settings=None, default_name=None):
        if isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        if settings is None:
            settings = {}
        settings.setdefault("name", default_name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = component(**settings)
        else:
            component = self.transform_component(component, settings)
        return component

    def add(self, component, *, settings=None, default_name=None):
        transformed = self.transform_item(
            component=component, default_name=default_name, settings=settings
        )
        self.push(transformed)

    def insert(self, idx, component):
        with self._lock:
            self._components.insert(idx, component)

    def discard(self, component):
        with self._lock:
            try:
                idx = self._components.index(component)
            except IndexError:
                pass
        self.pop(idx)

    def push(self, component):
        with self._lock:
            self._components.append(component)

    def pop(self, index=-1):
        with self._lock:
            return self._components.pop(index)

    def clear(self):
        with self._lock:
            self._components.clear()

    @property
    def size(self):
        return len(self._components)

    def __repr__(self):
        return f'<ComponentStack {self._components}>'


class Model:
    def __init_subclass__(
            cls,
            stack=None,
            from_members=None,
            settings=None,
            serializer=None
    ):
        if from_members is None:
            from_members = stack is None
        if stack is None:
            stack = ComponentStack()
        cls.stack = stack
        cls.settings = settings
        cls.serializer = serializer
        if from_members:
            for default_name, component in inspect.getmembers(cls):
                cls.add_component(component, default_name=default_name)

    def __init__(self, driver: str | Driver, engine=None):
        if engine is None:
            engine = get_global_engine()
        if isinstance(driver, str):
            driver = engine.get_driver(driver)
        self._state = driver(self)

    def __setitem__(self, key, value):
        self._state[key] = value

    def __getitem__(self, key, value):
        return self._state[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key, value):
        return self[key]

    @classmethod
    def add_component(cls, component, default_name=None):
        cls.stack.add(
            component=component,
            default_name=default_name,
            settings=cls.settings
        )
        return cls

    @classmethod
    def discard_component(cls, component):
        cls.stack.discard(component=component)
        return cls


def model(
        *components,
        stack=None,
        name=None,
        **settings
):
    if stack is None:
        stack = ComponentStack()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    return type(name, (Model,), {}, stack=stack)
