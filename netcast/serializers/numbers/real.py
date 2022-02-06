from __future__ import annotations

import abc
import functools
import math
import numbers
from typing import NamedTuple, Type, Literal

from netcast.constraints import RangeConstraint
from netcast.serializer import Serializer
from netcast.plugins.constrained import Constrained
from netcast.tools.collections import classproperty


__all__ = (
    "Bit",
    "Bool",
    "Byte",
    "Char",
    "Float16",
    "Float32",
    "Float64",
    "Half",
    "HalfByte",
    "Int",
    "Int128",
    "Int16",
    "Int256",
    "Int32",
    "Int512",
    "Int64",
    "Int8",
    "Long",
    "LongInt",
    "LongLong",
    "LongLongInt",
    "Nibble",
    "Primitive",
    "Real",
    "Short",
    "ShortInt",
    "Signed",
    "SignedByte",
    "SignedChar",
    "SignedInt",
    "SignedInt128",
    "SignedInt16",
    "SignedInt256",
    "SignedInt32",
    "SignedInt512",
    "SignedInt64",
    "SignedInt8",
    "SignedLong",
    "SignedLongInt",
    "SignedLongLong",
    "SignedLongLongInt",
    "SignedReal",
    "Tetrade",
    "Unsigned",
    "UnsignedByte",
    "UnsignedChar",
    "UnsignedInt",
    "UnsignedInt128",
    "UnsignedInt16",
    "UnsignedInt256",
    "UnsignedInt32",
    "UnsignedInt512",
    "UnsignedInt64",
    "UnsignedInt8",
    "UnsignedLong",
    "UnsignedLongInt",
    "UnsignedLongLong",
    "UnsignedLongLongInt",
    "UnsignedReal",
    "Bounds",
    "factorize_int_constraint",
    "int_type",
)


class Bounds(NamedTuple):
    min: numbers.Real
    max: numbers.Real


class Primitive(Serializer, abc.ABC):
    """Base class for all Python primitive types."""

    new_context = True


class Real(Primitive, Constrained, abc.ABC):
    bit_length = math.inf
    bounds = Bounds(-math.inf, math.inf)

    @classproperty
    def constraints(cls):
        return (RangeConstraint(**cls.bounds._asdict()),)


SignedReal = Real


class UnsignedReal(Real, abc.ABC):
    new_context = False
    bounds = Bounds(0, math.inf)


def _get_class_name(
    size: int, type_name: Literal["Int", "Float"], signed: bool = True
) -> str:
    name = ("Signed" if signed else "Unsigned") if type_name != "Float" else ""
    name += type_name
    if size:
        name += str(size)
    return name


class AnyInt(Real, abc.ABC):
    """Base integer type."""

    __load_type__ = int


AnySignedInt = AnyInt


class AnyUnsignedInt(UnsignedReal, abc.ABC):
    """Base unsigned integer type."""

    __load_type__ = int


def factorize_int_constraint(bit_length: int, signed: bool = True):
    if bit_length:
        pow2 = 2 ** bit_length
        if signed:
            pow2 //= 2
            min_val, max_val = -pow2, pow2 - 1
        else:
            min_val, max_val = 0, pow2 - 1
        constraint_bounds = Bounds(min_val, max_val)
    elif signed:
        constraint_bounds = AnySignedInt.bounds
    else:
        constraint_bounds = AnyUnsignedInt.bounds
    return RangeConstraint(bit_length=bit_length, **constraint_bounds._asdict())


@functools.lru_cache
def int_type(bit_length, signed=True) -> Type[AnyInt] | type:
    (constraint,) = constraints = (factorize_int_constraint(bit_length, signed=signed),)
    name = _get_class_name(bit_length or math.inf, type_name="Int", signed=signed)
    bases = (AnySignedInt if signed else AnyUnsignedInt, Constrained, abc.ABC)
    serializer = type(name, bases, {"constraints": constraints, "__module__": __name__})
    serializer.bounds = Bounds(constraint.cfg.min, constraint.cfg.max)
    serializer.bit_length = constraint.cfg.bit_length
    return serializer


Bool = Bit = int_type(1, signed=False)
Nibble = HalfByte = Tetrade = int_type(4, signed=False)

SignedInt8 = Int8 = int_type(8)
SignedInt16 = Int16 = int_type(16)
SignedInt32 = Int32 = int_type(32)
SignedInt64 = Int64 = int_type(64)
SignedInt128 = Int128 = int_type(128)
SignedInt256 = Int256 = int_type(256)
SignedInt512 = Int512 = int_type(512)

UnsignedInt8 = int_type(8, signed=False)
UnsignedInt16 = int_type(16, signed=False)
UnsignedInt32 = int_type(32, signed=False)
UnsignedInt64 = int_type(64, signed=False)
UnsignedInt128 = int_type(128, signed=False)
UnsignedInt256 = int_type(256, signed=False)
UnsignedInt512 = int_type(512, signed=False)

# A few aliases for the easier implementation of serializers in C-associated protocols.
# Let's (no please...) reinvent the wheel a bit!
Byte = SignedByte = Char = SignedChar = SignedInt8
UnsignedByte = UnsignedChar = UnsignedInt8

Short = ShortInt = Int16
Int = Long = LongInt = Int32
Signed = SignedInt = SignedLong = SignedLongInt = Int32
Unsigned = UnsignedInt = UnsignedLong = UnsignedLongInt = UnsignedInt32
LongLong = LongLongInt = SignedLongLong = SignedLongLongInt = Int64
UnsignedLongLong = UnsignedLongLongInt = UnsignedInt64


class _Float(Real, metaclass=abc.ABCMeta):
    __load_type__ = float


def float_type(bit_length, constraints=()):
    name = _get_class_name(bit_length, type_name="Float")
    env = {"__module__": __name__, "constraints": constraints, "bit_length": bit_length}
    serializer = type(name, (_Float, abc.ABC), env)
    return serializer


Float16 = float_type(16)
Float32 = float_type(32)
Float64 = float_type(64)

# Aliases
Half = Float16
Single = Float32
Double = Float64
