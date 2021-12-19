from __future__ import annotations
import sys
import types


extra_conversion_modules: dict[str, types.ModuleType] = {}


def get_conversion_keys():
    return dir(sys.modules[__name__]) + list(extra_conversion_modules)


def get_conversion_module():
    pass
