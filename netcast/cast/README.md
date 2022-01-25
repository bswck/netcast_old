# Ok, so what is it all for
The overall effect is meant to be like this:

sample 1.

```py
from netcast.cast import metadata
from netcast.cast.abc_datatypes import Auto, Byte
from netcast.cast.engine import get_engine


@metadata(
    rules=dict(
        exclude_constants=False,
        exclude_attrs=['SOME_UNSERIALIZED_CONSTANT']
    ),
    serialization=dict(
        some_nice_property=Byte(unsigned=True),
        some_cool_public_value=Auto,
        some_other_value=Byte  # signed
    ),
    recreation=dict(some_nice_property=metadata.recreation.setattr)
)
class SomeNiceObject:
    SOME_SERIALIZED_CONSTANT = 10
    SOME_UNSERIALIZED_CONSTANT = 0xdeadbeef

    def __init__(self):
        self._some_nice_private_value = self.SOME_CONSTANT
        self.some_cool_public_value = 'Hello world!'
        self.some_other_value = 0

    def __eq__(self, other):
        return all((
            # Check constants
            self.SOME_SERIALIZED_CONSTANT == other.SOME_SERIALIZED_CONSTANT,
            self.SOME_UNSERIALIZED_CONSTANT == other.SOME_UNSERIALIZED_CONSTANT,
            # Check private attrs
            self._some_nice_private_value == other._some_nice_private_value,
            # Check public attrs
            self.some_cool_public_value == other.some_cool_public_value,
            self.some_other_value == other.some_other_value,
            # Check properties
            self.some_nice_property == other.some_nice_property
        ))

    @property
    def some_nice_property(self):
        return self._some_nice_private_value

    @some_nice_property.setter
    def some_nice_property(self, value):
        self._some_nice_private_value = value

    def some_function(self):
        # do something...
        pass


foo = SomeNiceObject()

construct = get_engine('construct')
json = get_engine('json')
bar = construct.dumps(foo)
biz = json.dumps(foo)
assert bar == b'\x0AHello world!\x00\x00\x0A'
assert biz == '''{"SOME_SERIALIZED_CONSTANT": 10,"some_cool_public_value": "Hello world!","some_other_value": 0,"some_nice_property": 10}'''
assert foo == construct.loads(SomeNiceObject, bar)
assert foo == json.loads(SomeNiceObject, biz)
```

sample 2.

```py
from netcast.cast import metadata
from netcast.cast.engine import get_engine
from dataclasses import dataclass, field


@metadata.array
@dataclass
class SomeObject:
    me: int = 0

    @metadata.array(max_size=10)
    @dataclass
    class SomeNestedObject:
        me: int = 0

    members: list[SomeNestedObject] = field(default_factory=list)


foo = [
    SomeObject(
        1, [
            SomeObject.SomeNestedObject(10),
            SomeObject.SomeNestedObject(11),
            SomeObject.SomeNestedObject(12),
            SomeObject.SomeNestedObject(13),
            SomeObject.SomeNestedObject(14),
        ]
    ),
    SomeObject(
        2, [
            SomeObject.SomeNestedObject(0)
        ]
    )
]

engine = get_engine('construct')
bar = engine.dumps(foo)
assert bar == b'\x00\x05\x0A\x0B\x0C\x0D\x0E\x02\x01\x00'
assert foo == engine.load(bar)
```
