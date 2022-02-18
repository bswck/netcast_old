from __future__ import annotations  # Python 3.8

import construct
import netcast as nc


class Interface(nc.Interface):
    dump_type = bytes

    def __init__(self, *, name=None, coercion_flags=0, **settings):
        super().__init__(name=name, coercion_flags=coercion_flags, **settings)
        self.compiled = settings.get("compiled", not driver.DEBUG)

    @property
    def impl(self):
        impl = self._impl
        if self.compiled:
            impl = impl.compile()
        if self.name is not None and getattr(impl, "name", None) != self.name:
            impl = construct.Renamed(impl, self.name)
        return impl

    @property
    def driver(self):
        return driver


class Integer(Interface):
    __netcast_origin__ = nc.Integer

    def __init__(self, name=None, **settings):
        super().__init__(name=name, **settings)
        self.bit_size = self.settings.get("bit_size")
        self.signed = self.settings.get("signed", True)

        cpu_sized = self.settings.get("cpu_sized", True)
        big_endian = self.settings.get("big_endian", False)
        little_endian = self.settings.get("little_endian", True)
        native_endian = self.settings.get("native_endian", False)

        if cpu_sized and any(map(callable, (big_endian, little_endian, native_endian))):
            cpu_sized = False

        self.cpu_sized = cpu_sized
        self.little = little_endian
        self.big = big_endian
        self.native = native_endian

        impl = None
        if self.bit_size:
            if cpu_sized:
                impl = self.get_format_field()
                self.cpu_sized = False
            if impl is None:
                impl = self.get_bytes_integer()
        if impl is None:
            raise NotImplementedError(f"construct does not support {type(self).__name__}")
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
            byte_length, signed=self.signed, swapped=self.get_swapped()
        )

    def get_format_field(self):
        type_name = "Int" + str(self.bit_size) + "us"[self.signed]
        if self.big:
            type_name += "b"
        elif self.little:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


class FloatingPoint(Interface):
    __netcast_origin__ = nc.FloatingPoint


class Sequence(Interface):
    __netcast_origin__ = nc.ModelSerializer

    def __init__(self, *fields, name=None, **settings):
        super().__init__(name=name, **settings)
        self._impl = construct.Sequence(*self.get_impls(fields, settings))


class Array(Interface):
    __netcast_origin__ = nc.ModelSerializer

    def __init__(
            self,
            data_type,
            *,
            name=None,
            **settings
    ):
        super().__init__(name=name, **settings)
        size = self.settings.get("size")
        prefixed = self.settings.get("prefixed", False)
        lazy = self.settings.get("lazy", False)
        compiled = self.settings.get("compiled", False)

        if prefixed and lazy:
            raise ValueError("array can't be prefixed and lazy at the same time")

        if size is None:
            size = driver.UnsignedInt8(compiled=compiled).impl

        self.data_type = data_type
        self.data_type_impl = data_type_impl = self.get_impl(data_type, **settings)

        if prefixed:
            if isinstance(size, int) and 0 <= size < 256:
                size = construct.Const(bytes([size]))
            else:
                raise ValueError("expected a netcast data type!")

            self._impl = construct.PrefixedArray(size, data_type_impl)

        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError(
                    "expected an integer or a callable that returns integer"
                )

            self._impl = construct.LazyArray(size, data_type_impl)

        else:
            self._impl = construct.Array(size, data_type_impl)


class Struct(Interface):
    __netcast_origin__ = nc.ModelSerializer

    def __init__(
            self, *fields, name=None, **settings
    ):
        super().__init__(name=name, **settings)

        impls = self.get_impls(fields, self.settings)
        alignment_modulus = self.settings.get("alignment_modulus")

        if alignment_modulus is None:
            impl = construct.Struct(*impls)
        else:
            impl = construct.AlignedStruct(alignment_modulus, *impls)

        self._impl = impl


class ConstructDriver(nc.Driver):
    IntegerInterface = nc.interface(Integer)
    FloatingPointInterface = nc.interface(FloatingPoint)
    SequenceInterface = nc.interface(Sequence)
    ArrayInterface = nc.interface(Array)
    StructInterface = nc.interface(Struct)

    Integer = IntegerInterface(nc.Integer)
    FloatingPoint = FloatingPointInterface(nc.FloatingPoint)

    ListSequence = SequenceInterface(nc.List)
    TupleSequence = SequenceInterface(nc.Tuple)
    SetSequence = SequenceInterface(nc.Set)
    FrozenSetSequence = SequenceInterface(nc.FrozenSet)
    Sequence = ListSequence

    ListArray = ArrayInterface(nc.List)
    TupleArray = ArrayInterface(nc.Tuple)
    SetArray = ArrayInterface(nc.Set)
    FrozenSetArray = ArrayInterface(nc.FrozenSet)
    Array = ListArray

    DictStruct = StructInterface(nc.Dict)
    MappingProxyStruct = StructInterface(nc.MappingProxy)
    SimpleNamespaceStruct = StructInterface(nc.SimpleNamespace)
    Struct = DictStruct

    default_model_serializer = Struct


driver = ConstructDriver


@driver.get_model_serializer.register(Array)
def get_array_serializer(_, serializer, components=(), settings=None):
    if settings is None:
        settings = {}
    if len(components) != 1:
        raise ValueError("Array() takes exactly 1 argument")
    return serializer(*components, **settings)
