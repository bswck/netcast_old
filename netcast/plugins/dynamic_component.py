from jaraco.collections import Least, Greatest

from netcast.constants import Break
from netcast.plugin import Plugin, export


class DynamicComponent(Plugin):
    @export(call_before="dump", initial_shaping=True)
    def determine_dump(self, dump, **kwargs):
        return (dump,), kwargs

    @export(call_before="load", initial_shaping=True)
    def determine_load(self, load, **kwargs):
        return (load,), kwargs


class Versioned(Plugin, DynamicComponent):
    @export(call_after="setup")
    def setup_plugin(self):
        self.cfg.setdefault("incompat_break", Break.SKIP)
        self.cfg.setdefault("version", Greatest())

    def determine_break(self, obj, **kwargs):
        ok = (obj,), kwargs
        context = kwargs.get('context', {})
        is_compatible = context.get('version', Least()) <= self.cfg.version
        if context is None or is_compatible:
            return ok
        return (self.cfg.incompat_break,), kwargs

    @export(call_before="dump", initial_shaping=True)
    def determine_dump(self, dump, **kwargs):
        return self.determine_break(dump, **kwargs)

    @export(call_before="load", initial_shaping=True)
    def determine_load(self, load, **kwargs):
        return self.determine_break(load, **kwargs)
