from __future__ import annotations

import dataclasses
import functools
import threading
import typing

from netcast.model import Model
from netcast.constants import MISSING

if typing.TYPE_CHECKING:
    from typing import Any
    from netcast import Driver, Engine


lock = threading.RLock()


class _StateTraversable:
    @functools.cached_property
    def branches(self):
        return {}

    @functools.lru_cache
    def __getitem__(self, name):
        return BranchState(
            model=self._model[name],
            owner=self,
            driver=self._driver,
            name=name
        )

    def __getattr__(self, name):
        return self[name]


@dataclasses.dataclass
class State(_StateTraversable):
    model: Model
    engine: Engine
    driver: typing.Type[Driver]


@dataclasses.dataclass
class BranchState(_StateTraversable):
    model: Model
    driver: typing.Type[Driver]
    owner: _StateTraversable
    name: str
    value: Any = MISSING

    def __post_init__(self):
        with lock:
            self.owner.branches.setdefault(self.name, self)

    def set_driver(self, driver=None):
        self.driver = self.owner.engine.get_driver(driver)

    def __call__(self, value):
        self.value = value
        return self.owner
