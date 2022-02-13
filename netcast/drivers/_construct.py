from __future__ import annotations

import functools
import operator

import construct
import netcast as nc


DRIVER_NAME = "construct"


class ConstructInterface:
    _impl: construct.Construct
    compiled: bool
    load_type: type

    def __init__(self, compiled=False, force_load_type=True):
        self.compiled = compiled
        self.force_load_type = force_load_type

    @functools.cached_property
    def impl(self):
        if self.compiled:
            return self._impl.compile()
        return self._impl

    def _load(self, dump, *, context=None):
        if context is None:
            context = {}
        load = self.impl.parse(dump, **context)
        if self.force_load_type:
            load = self._coerce_load_type(load)
        return load

    def _coerce_load_type(self, load):
        factory = getattr(self, "factory", self.load_type)
        return factory(load)

    def _dump(self, load, *, context=None, stream=None):
        if context is None:
            context = {}
        if stream is not None:
            context['_io'] = stream
        return self.impl.build(load, **context)


class Number(nc.Number, ConstructInterface):
    def __init__(
            self, 
            big_endian=None,
            little_endian=None,
            native_endian=None,
            cpu_sized=True,
            compiled=False
    ):
        ConstructInterface.__init__(self, compiled)

        if cpu_sized and any(map(callable, (big_endian, little_endian, native_endian))):
            cpu_sized = False

        self.little = little_endian
        self.big = big_endian
        self.native = native_endian
        self.cpu_sized = cpu_sized

        impl = None

        if cpu_sized:
            impl = self.get_format_field()
            self.cpu_sized = False

        if impl is None:
            impl = self.get_bytes_integer()

        if impl is None:
            raise NotImplementedError(f"construct does not support {self}")

        self._impl = impl

    def get_swapped(self):
        if self.big is None and self.native is None and self.little is not None:
            return self.little
        if self.big is None and self.native is not None:
            return self.native
        return True if self.big is None else self.big

    def get_bytes_integer(self):
        byte_length = self.bit_size >> 3
        return construct.BytesInteger(
            byte_length, signed=self.signed,
            swapped=self.get_swapped()
        )

    def get_format_field(self):
        type_name = "Int" if self.load_type is int else "Float"
        type_name += str(self.bit_size)
        type_name += ("s" if self.signed else "u") if self.load_type is int else ""
        if self.big:
            type_name += "b"
        elif self.little:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


class Sequence(nc.BulkSerializer, ConstructInterface):
    def __init__(
            self,
            *fields,
            compiled=False
    ):
        ConstructInterface.__init__(self, compiled)
        self._impl = construct.Sequence(*map(operator.attrgetter('impl'), fields))


class Array(nc.BulkSerializer, ConstructInterface):
    def __init__(
            self,
            data_type,
            size=None,
            prefixed=False,
            lazy=False,
            compiled=False
    ):
        ConstructInterface.__init__(self, compiled)

        if prefixed and lazy:
            raise ValueError("array can't be prefixed and lazy at the same time")

        if size is None:
            size = driver.UnsignedInt8(compiled=compiled).impl

        if prefixed:
            if isinstance(size, int):
                size = construct.Const(bytes([size]))

            self._impl = construct.PrefixedArray(size, data_type.impl)

        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError("expected an integer or a callable that returns integer")

            self._impl = construct.LazyArray(size, data_type.impl)

        else:
            self._impl = construct.Array(size, data_type.impl)


class Struct(nc.BulkSerializer, ConstructInterface):
    def __init__(self, *fields, compiled=False):
        ConstructInterface.__init__(self, compiled)
        self._impl = construct.Struct(*map(operator.attrgetter('impl'), fields))


class ConstructDriver(nc.Driver):
    NumberImpl = nc.adapter(Number)
    SequenceImpl = nc.adapter(Sequence)
    ArrayImpl = nc.adapter(Array)

    SignedInt8 = NumberImpl(nc.SignedInt8)
    SignedInt16 = NumberImpl(nc.SignedInt16)
    SignedInt32 = NumberImpl(nc.SignedInt32)
    SignedInt64 = NumberImpl(nc.SignedInt64)
    SignedInt128 = NumberImpl(nc.SignedInt128)
    SignedInt256 = NumberImpl(nc.SignedInt256)
    SignedInt512 = NumberImpl(nc.SignedInt512)
    UnsignedInt8 = NumberImpl(nc.UnsignedInt8)
    UnsignedInt16 = NumberImpl(nc.UnsignedInt16)
    UnsignedInt32 = NumberImpl(nc.UnsignedInt32)
    UnsignedInt64 = NumberImpl(nc.UnsignedInt64)
    UnsignedInt128 = NumberImpl(nc.UnsignedInt128)
    UnsignedInt256 = NumberImpl(nc.UnsignedInt256)
    Float16 = NumberImpl(nc.Float16)
    Float32 = NumberImpl(nc.Float32)
    Float64 = NumberImpl(nc.Float64)
    ListSequence = SequenceImpl(nc.List)
    TupleSequence = SequenceImpl(nc.Tuple)
    SetSequence = SequenceImpl(nc.Set)
    FrozenSetSequence = SequenceImpl(nc.FrozenSet)
    Array = Array
    Dict = Struct = Struct


driver = ConstructDriver


if __name__ == '__main__':
    arr = [3, 5, 255, 3, 64, 23, 43, 5, 0, 42]
    comp = driver.Array(data_type=driver.UnsignedInt8(), size=10)
    cs = comp.dump(arr)
    print(cs)
    print(comp.load(cs))
