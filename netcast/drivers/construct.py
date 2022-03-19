from __future__ import annotations  # Python 3.8

import construct
import netcast as nc


class Interface(nc.Interface):
    def __init__(self, **settings):
        self.compiled = settings.setdefault("compiled", not self.driver.DEBUG)
        super().__init__(**settings)

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
        return ConstructDriver

    def _load(self, obj, settings, **kwargs):
        return self.impl.parse(obj)

    def _dump(self, obj, settings, **kwargs):
        return self.impl.build(obj)


class Sequence(Interface):
    orig_cls = nc.ModelSerializer

    def __init__(self, *fields, **settings):
        self._impl = construct.Sequence(*self.get_impls(fields, settings))
        super().__init__(**settings)


class Array(Interface):
    orig_cls = nc.ModelSerializer

    def __init__(self, data_type, /, **settings):
        size = settings.get("size")
        if size is None:
            size = ConstructDriver.UnsignedInt8(compiled=self.compiled).impl
        self.size = settings.setdefault("size", size)
        self.prefixed = settings.setdefault("prefixed", False)
        self.lazy = settings.setdefault("lazy", False)
        self.compiled = settings.setdefault("compiled", False)
        self.data_type = data_type
        self.data_type_impl = self.get_impl(data_type, **settings)
        super().__init__(**settings)

    def _configure(self, prefixed, lazy):
        size = self.size

        if prefixed and lazy:
            raise ValueError(
                "a binary array can't be prefixed and lazy at the same time"
            )

        if prefixed:
            if isinstance(size, int) and 0 <= size < 256:
                size = construct.Const(bytes([size]))
            else:
                raise ValueError("expected a netcast data type!")
            self._impl = construct.PrefixedArray(size, self.data_type_impl)
        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError(
                    "expected an integer or a callable that returns integer"
                )
            self._impl = construct.LazyArray(size, self.data_type_impl)
        else:
            self._impl = construct.Array(size, self.data_type_impl)


class Struct(Interface):
    orig_cls = nc.ModelSerializer

    def __init__(self, *fields, **settings):
        self.alignment_modulus = settings.setdefault("alignment_modulus", None)
        self.impls = self.get_impls(fields, settings)
        super().__init__(**settings)

    def _configure(self, alignment_modulus):
        if alignment_modulus is None:
            impl = construct.Struct(*self.impls)
        else:
            impl = construct.AlignedStruct(alignment_modulus, *self.impls)
        self._impl = impl


class ConstructDriver(nc.Driver):
    SequenceInterface = nc.driver_interface(Sequence)
    ArrayInterface = nc.driver_interface(Array)
    StructInterface = nc.driver_interface(Struct)

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


@ConstructDriver.register
class Integer(Interface):
    orig_cls = nc.Integer
    bit_size: int
    signed: bool

    def __init__(self, **settings):
        self.signed = settings.setdefault("signed", True)
        self.cpu_sized = settings.setdefault("cpu_sized", True)
        self.little_endian = settings.setdefault("little_endian", True)
        self.big_endian = settings.setdefault("big_endian", False)
        self.native_endian = settings.setdefault("native_endian", False)
        self.bit_size = settings.get("bit_size", 32)
        super().__init__(**settings)

    def _configure(
        self,
        *,
        signed,
        cpu_sized,
        big_endian,
        little_endian,
        native_endian,
    ):
        if cpu_sized and any(map(callable, (big_endian, little_endian, native_endian))):
            cpu_sized = False

        impl = None

        if self.bit_size:
            if cpu_sized:
                impl = self.get_format_field()
                cpu_sized = False
            if impl is None:
                impl = self.get_bytes_integer()

        if impl is None:
            raise NotImplementedError(
                f"construct does not support {type(self).__name__}"
            )

        self.settings.update(cpu_sized=cpu_sized)
        self._impl = impl

    def get_swapped(self):
        if (
            self.big_endian is None
            and self.native_endian is None
            and self.little_endian is not None
        ):
            return self.little_endian
        if self.big_endian is None and self.native_endian is not None:
            return self.native_endian
        return True if self.big_endian is None else self.big_endian

    def get_bytes_integer(self):
        byte_length = self.bit_size >> 3
        return construct.BytesInteger(
            byte_length, signed=self.signed, swapped=self.get_swapped()
        )

    def get_format_field(self):
        type_name = "Int" + str(self.bit_size) + "us"[self.signed]
        if self.big_endian:
            type_name += "b"
        elif self.little_endian:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


class _EncodingHack:
    def __init__(self):
        self._unit_cache = construct.possiblestringencodings.copy()

    def encoding_unit(self, encoding):
        """Create the encoding unit for a given encoding."""
        unit = self._unit_cache.get(encoding)
        if unit is None:
            unit = len("\x00".encode(encoding))
            self._unit_cache[encoding] = unit
        return bytes(unit)

    def c_string(self, encoding):
        encoding = encoding.casefold()
        macro = construct.StringEncoded(
            construct.NullTerminated(
                construct.GreedyBytes, term=self.encoding_unit(encoding)
            ),
            encoding,
        )

        def _netcast_emitfulltype(_ksy, _bitwise):
            return dict(type="strz", encoding=encoding)

        macro._emitfulltype = _netcast_emitfulltype
        return macro

    def padded_string(self, length, encoding):
        encoding = encoding.casefold()
        macro = construct.StringEncoded(
            construct.FixedSized(
                length,
                construct.NullStripped(
                    construct.GreedyBytes, pad=self.encoding_unit(encoding)
                ),
            ),
            encoding,
        )

        def _netcast_emitfulltype(_ksy, _bitwise):
            return dict(size=length, type="strz", encoding=encoding)

        macro._emitfulltype = _netcast_emitfulltype
        return macro


@ConstructDriver.register
class String(Interface):
    orig_cls = nc.String
    default_encoding = "ASCII"
    encoding_hack = _EncodingHack()

    def __init__(self, **settings):
        self.null_terminated = settings.setdefault("null_terminated", True)
        self.encoding = settings.setdefault("encoding", self.default_encoding)
        self.pascal = settings.setdefault("pascal", False)
        self.greedy = settings.setdefault("greedy", False)
        self.padded = settings.setdefault("padded", False)
        self.size = settings.setdefault("size", None)
        super().__init__(**settings)

    def _configure(self, size, null_terminated, pascal, greedy, padded, encoding):
        impl = None
        if pascal or null_terminated:
            if null_terminated:
                impl = self.encoding_hack.c_string(encoding)
            elif padded:
                if size is None:
                    raise ValueError(
                        "undefined size for a fixed-size string serializer"
                    )
                impl = self.encoding_hack.padded_string(size, encoding)
            elif pascal:
                if size is None:
                    size = self.get_impl(self.driver.Int8(signed=False))
                impl = construct.PascalString(size, encoding)
            elif greedy:
                impl = construct.GreedyString(encoding)
        if impl is None:
            raise ValueError("invalid string serializer configuration")
        self._impl = impl


@ConstructDriver.register
class FloatingPoint(Interface):
    orig_cls = nc.FloatingPoint

    def __init__(self, **settings):
        self.bit_size = settings.get("bit_size", 32)  # float, double is 64
        super().__init__(**settings)

    def _configure(
        self,
        *,
        big_endian,
        little_endian,
        native_endian,
    ):
        impl = None
        if self.bit_size:
            impl = self.get_format_field()
        if impl is None:
            raise NotImplementedError(
                f"construct does not support {type(self).__name__}"
            )
        self._impl = impl

    def get_format_field(self):
        type_name = "Float" + str(self.bit_size)
        if self.big_endian:
            type_name += "b"
        elif self.little_endian:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


@ConstructDriver.get_model_serializer.register(Array)
def get_array_serializer(_, serializer, components=(), settings=None):
    if settings is None:
        settings = {}
    if len(components) != 1:
        raise ValueError("construct::Array() takes exactly 1 argument")
    return serializer(*components, **settings)
