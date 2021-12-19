import collections

from netcast import cast
from traitlets import TraitType


class ConversionType(TraitType):
    """
    A trait type for all interpreters.
    Shares the information about available cast.
    """

    _conversion_registry = collections.defaultdict(list)

    def __init__(self, conversion_key, *args, **kwargs):
        conversion_keys = cast.get_conversion_keys()
        if conversion_key not in conversion_keys:
            raise ValueError(
                f'invalid conversion key {conversion_key!r}. '
                f'Did you forget to register it?'
            )
        self._conversion_registry[conversion_key].append(self)
        super().__init__(*args, **kwargs)

    def instance_init(self, obj):
        ConversionType._conversion_registry[obj.__name__] = obj  # registers the interpreter
