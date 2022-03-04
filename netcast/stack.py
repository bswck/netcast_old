from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from netcast import GREATEST, LEAST
from netcast.tools.inspection import combined_getattr
from netcast.serializer import Serializer


if TYPE_CHECKING:
    from netcast.model import Model, ComponentArgumentT, ComponentT


__all__ = ("ComponentStack", "FilteredComponentStack", "VersionAwareComponentStack")


class ComponentStack:
    def __init__(self):
        self._components = []
        self._lock = threading.RLock()

    @classmethod
    def transform_submodel(cls, submodel) -> Model:
        return submodel

    @classmethod
    def transform_serializer(
        cls, component: Serializer, settings: dict | None = None
    ) -> Serializer:
        if settings is None:
            settings = {}
        if getattr(component, "taken", False):
            return component
        component = component(**settings)
        component.taken = True
        return component

    def transform_component(
        self, component: ComponentArgumentT, *, settings=None, default_name=None
    ) -> ComponentT | None:
        from netcast.model import Model
        if settings is None:
            settings = {}
        settings.setdefault("name", default_name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = component(**settings)
        elif isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        else:
            assert isinstance(component, Serializer)
            component = self.transform_serializer(component, settings)
        return component

    def add(
        self,
        component: ComponentArgumentT,
        *,
        settings: dict | None = None,
        default_name: str | None = None,
    ):
        """Push with transform."""
        if isinstance(settings, dict):
            settings = settings.copy()
        transformed = self.transform_component(
            component=component, default_name=default_name, settings=settings
        )
        self.push(transformed)
        return transformed

    def insert(self, idx: int, component: ComponentT):
        self._lock.acquire()
        self._components.insert(idx, component)
        self._lock.release()

    def discard(self, component: ComponentT):
        self._lock.acquire()
        try:
            idx = self._components.index(component)
        except IndexError:
            idx = None
        self._lock.release()
        if idx is not None:
            self.pop(idx)

    def push(self, component: ComponentT):
        self._lock.acquire()
        self._components.append(component)
        self._lock.release()

    def pop(self, index: int = -1) -> ComponentT | None:
        self._lock.acquire()
        obj = self._components.pop(index)
        self._lock.release()
        return obj

    def get(self, index: int = -1, settings: dict | None = None) -> ComponentT | None:
        self._lock.acquire()
        try:
            obj = self._components[index]
        except IndexError:
            obj = None
        self._lock.release()
        return obj

    def clear(self):
        self._lock.acquire()
        self._components.clear()
        self._lock.release()

    @property
    def size(self) -> int:
        return len(self._components)

    def get_matching_components(self, settings=None) -> dict[str, ComponentT]:
        if settings is None:
            settings = {}
        matched = {}
        for idx in range(self.size):
            component = self.get(idx, settings)
            if component is not None:
                matched[component.name] = component
        return matched

    def __del__(self):
        for component in self._components:
            component.taken = False
        self._components.clear()

    def __repr__(self) -> str:
        name = type(self).__name__
        return f"<{name} {self._components}>"


class FilteredComponentStack(ComponentStack):
    def predicate(self, component, settings):
        return True

    def get(self, index=-1, settings=None):
        if settings is None:
            settings = {}
        component = super().get(index, settings)
        if component is None:
            return component
        if not self.predicate(component, settings):
            component = None
        return component


class VersionAwareComponentStack(FilteredComponentStack):
    """
    A very simple and basic versioning layer.  `foo = Int64(version_added=1, version_removed=5)`
    will inform the model to include `foo` component only if `1 <= <version> <= 5`.
    """

    def __init__(
        self,
        *,
        settings_version_field="version",
        since_field="settings[version_added]",
        until_field="settings[version_removed]",
        default_version=GREATEST,
        default_since_version=LEAST,
        default_until_version=GREATEST,
    ):
        super().__init__()
        self.settings_version_field = settings_version_field
        self.since_version_field = since_field
        self.until_version_field = until_field
        self.default_version = default_version
        self.default_since_version = default_since_version
        self.default_until_version = default_until_version

    def predicate_version(self, component, settings):
        version = settings.get(self.settings_version_field, self.default_version)
        since_version = combined_getattr(
            component, self.since_version_field, self.default_since_version
        )
        until_version = combined_getattr(
            component, self.until_version_field, self.default_until_version
        )
        introduced = since_version <= version
        up_to_date = until_version >= version
        return introduced and up_to_date

    def predicate(self, component, settings):
        return self.predicate_version(component, settings)
