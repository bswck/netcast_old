from __future__ import annotations

import copy

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.tools.contexts import Context


class Serializer:
    """
    A base class for all serializers. A good serializer can dump and load stuff.
    """
    load_type = MISSING
    dump_type = MISSING

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
                raise NetcastError(f"dumping failed: {exc}") from exc

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
                raise NetcastError(f"loading failed: {exc}") from exc

    def __call__(self, **override) -> Serializer:
        new = copy.copy(self)
        for attr, val in override:
            setattr(new, attr, val)
        return new
