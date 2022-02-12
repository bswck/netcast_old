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
        self._mutex = threading.RLock()

    @classmethod
    def transform_submodel(cls, submodel):
        return submodel

    @classmethod
    def transform_component(cls, component, cfg=None):
        if cfg is None:
            cfg = {}
        return component.copy(**cfg)

    def transform_item(self, component, *, cfg=None, default_name=None):
        if isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        if cfg is None:
            cfg = {}
        cfg.setdefault('name', default_name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = component(**cfg)
        else:
            component = self.transform_component(component, cfg)
        return component

    def insert(self, idx, component):
        with self._mutex:
            self._components.insert(idx, component)

    def push_transformed(self, component, *, cfg=None, default_name=None):
        transformed = self.transform_item(
            component=component, default_name=default_name, cfg=cfg
        )
        self.push(transformed)

    def discard(self, component):
        with self._mutex:
            try:
                idx = self._components.index(component)
            except IndexError:
                pass
        self.pop(idx)

    def push(self, component):
        with self._mutex:
            self._components.append(component)

    def pop(self, index=-1):
        with self._mutex:
            return self._components.pop(index)

    def clear(self):
        with self._mutex:
            self._components.clear()

    @property
    def size(self):
        return len(self._components)

    def __repr__(self):
        return f'<{type(self).__name__}{self._components}>'


class Model:
    def __init_subclass__(cls, stack=None, push_members=None, cfg=None):
        if push_members is None:
            push_members = stack is None
        if stack is None:
            stack = ComponentStack()
        cls.stack = stack
        cls.cfg = cfg
        if push_members:
            for default_name, component in inspect.getmembers(cls):
                cls.add_component(component, default_name=default_name)

    def __init__(self, driver: str | Driver, engine=None):
        if engine is None:
            engine = get_global_engine()
        if isinstance(driver, str):
            driver = engine.get_driver(driver)
        self._state = driver(self).state

    @classmethod
    def add_component(cls, component, default_name=None):
        cls.stack.push_transformed(
            component=component,
            default_name=default_name,
            cfg=cls.cfg
        )
        return cls

    @classmethod
    def discard_component(cls, component):
        cls.stack.discard(component=component)
        return cls

    def __setitem__(self, key, value):
        self._state[key] = value

    def __getitem__(self, key, value):
        return self._state[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key, value):
        return self[key]


def model(
        *components,
        stack=None,
        name=None,
        **cfg
):
    if stack is None:
        stack = ComponentStack()
    for component in components:
        stack.push_transformed(component, cfg=cfg)
    if name is None:
        name = "model_" + str(id(stack))
    return type(name, (Model,), {}, stack=stack)
