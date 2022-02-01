from __future__ import annotations

import abc
import collections
import functools
import math
from typing import Type, Literal

from netcast.cast.serializer import Serializer, Constraint, ConstraintError
from netcast.cast.plugins.constrained import Constrained
from netcast.toolkit import strings
from netcast.toolkit.symbol import Symbol
from netcast.toolkit.collections import classproperty

bounds = collections.namedtuple('bounds', 'min_val max_val')


class MinMaxConstraint(Constraint):
    def validate_load(self, load):
        min_val, max_val = self.cfg.min_val, self.cfg.max_val
        if min_val <= load <= max_val:
            return load
        min_val, max_val = map(
            functools.partial(strings.truncate, stats=None),
            map(str, (min_val, max_val))
        )
        raise ConstraintError(
            f'loaded object is out of serialization bounds [{min_val}, {max_val}]'
        )


class Primitive(Serializer, abc.ABC):
    """Base class for all Python primitive types."""
    __load_type__ = Symbol('Primitive')

    new_context = True


class Real(Primitive, Constrained, abc.ABC):
    __load_type__ = Symbol('Real')

    bit_length = math.inf
    bounds = bounds(-math.inf, math.inf)

    @classproperty
    def constraints(self):
        return MinMaxConstraint(**self.bounds._asdict()),


SignedReal = Real


class UnsignedReal(Real, abc.ABC):
    __load_type__ = Symbol('UnsignedReal')

    new_context = False
    bounds = bounds(0, math.inf)


def _get_class_name(
        size: int,
        type_name: Literal['Int', 'Float'],
        signed: bool = True
) -> str:
    name = 'Signed' if signed else 'Unsigned'
    name += type_name
    if size:
        name += str(size)
    return name


class BaseInt(Real, abc.ABC):
    """Base integer type."""
    __load_type__ = int


SignedBaseInt = BaseInt


class UnsignedBaseInt(UnsignedReal, abc.ABC):
    """Base unsigned integer type."""
    __load_type__ = int


@functools.lru_cache
def factorize_int_constraint(bit_length: int, signed: bool = True):
    if bit_length:
        pow2 = 2 ** bit_length
        if signed:
            pow2 //= 2
            min_val, max_val = -pow2, pow2 - 1
        else:
            min_val, max_val = 0, pow2 - 1
        constraint_bounds = bounds(min_val, max_val)
    elif signed:
        constraint_bounds = BaseInt.bounds
    else:
        constraint_bounds = UnsignedBaseInt.bounds
    return MinMaxConstraint(bit_length=bit_length, **constraint_bounds._asdict())


def int_serializer(bit_length, signed=True) -> Type[BaseInt] | type:
    constraint, = constraints = factorize_int_constraint(bit_length, signed=signed),
    name = _get_class_name(bit_length or math.inf, type_name='Int', signed=signed)
    bases = (SignedBaseInt if signed else UnsignedBaseInt, Constrained, abc.ABC)
    serializer = type(name, bases, {'constraints': constraints})
    serializer.bounds = bounds(constraint.cfg.min_val, constraint.cfg.max_val)
    serializer.bit_length = constraint.cfg.bit_length
    return serializer


Bool = Bit = int_serializer(1, signed=False)
Nibble = HalfByte = Tetrade = int_serializer(4, signed=False)

SignedInt8 = Int8 = int_serializer(8)
SignedInt16 = Int16 = int_serializer(16)
SignedInt32 = Int32 = int_serializer(32)
SignedInt64 = Int64 = int_serializer(64)
SignedInt128 = Int128 = int_serializer(128)
SignedInt256 = Int256 = int_serializer(256)
SignedInt512 = Int512 = int_serializer(512)

UnsignedInt8 = int_serializer(8, signed=False)
UnsignedInt16 = int_serializer(16, signed=False)
UnsignedInt32 = int_serializer(32, signed=False)
UnsignedInt64 = int_serializer(64, signed=False)
UnsignedInt128 = int_serializer(128, signed=False)
UnsignedInt256 = int_serializer(256, signed=False)
UnsignedInt512 = int_serializer(512, signed=False)

# A few aliases for the easier implementation of serializers in C-associated protocols.
# Let's (no please...) reinvent the wheel a bit!
Byte = SignedByte = Char = SignedChar = SignedInt8
UnsignedByte = UnsignedChar = UnsignedInt8

Short = ShortInt = Int16
Int = Long = LongInt = Int32
Signed = SignedInt = SignedLong = SignedLongInt = Int32
Unsigned = UnsignedInt = UnsignedLong = UnsignedLongInt = UnsignedInt32
LongLong = SignedLongLong = SignedLongLongInt = Int64
UnsignedLongLong = UnsignedLongLongInt = UnsignedInt64


class BaseFloat(Real, abc.ABC):
    __load_type__ = float


SignedBaseFloat = BaseFloat


class UnsignedBaseFloat(UnsignedReal, abc.ABC):
    __load_type__ = float
