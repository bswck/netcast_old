from __future__ import annotations

import abc
import copy
import sys
from typing import Any, ClassVar, Type

from netcast.constants import MISSING
from netcast.exceptions import ArrangementConstructionError, NetcastError
from netcast.plugin import Plugin
from netcast.tools import strings
from netcast.tools.arrangements import ClassArrangement
from netcast.tools.contexts import Context, DoublyLinkedListContextMixin, wrap_method
from netcast.tools.collections import AttributeDict


class DataTypeRegistry(DoublyLinkedListContextMixin, AttributeDict):
    """Data types registry."""

    def __repr__(self):
        super_type = getattr(getattr(self.get('_'), 'cls', None), '__name__', MISSING)
        return '\n'.join((
            f'Supertype: {super_type}',
            f'Data type: {self.cls.__name__}'
        ))


class Serializer:
    """
    A base class for all serializers. A good serializer can dump and load stuff.
    """

    def __init__(self, **settings: Any):
        super().__init__()
        self.settings: AttributeDict[str, Any] = AttributeDict(settings)
        self.setup()

    def setup(self):
        """Simple setup callback. Does nothing by default."""

    def copy(self, deep=False, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        """Copy this type."""
        if deep:
            new_cfg = {**copy.deepcopy(self.settings), **cfg}
        else:
            new_cfg = self.settings
            new_cfg.update(cfg)
        new = type(self)(**new_cfg)
        return new

    def dump(self, load, *, context: Context | None = None, **kwargs):
        """
        Dump a load.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        try:
            dump = getattr(self, "_dump")
        except AttributeError as e:
            raise NotImplementedError from e
        else:
            try:
                return dump(load, context=context, **kwargs)
            except Exception as exc:
                raise NetcastError from exc

    def load(self, dump, *, context: Context | None = None, **kwargs):
        """
        Load from a dump.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        try:
            load = getattr(self, "_load")
        except AttributeError:
            raise NotImplementedError
        else:
            try:
                return load(dump, context=context, **kwargs)
            except Exception as exc:
                raise NetcastError from exc

    def __call__(self, **settings: Any) -> Serializer:
        return self.copy(**settings)


