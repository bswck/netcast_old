import functools
import operator
from typing import Type, TypeVar, Sequence, Any, MutableMapping, Optional, Callable

import construct as cs


def _dunder(string):
    return '__' + string + '__'


STRIPPED_IGNORE_ATTRS = (
    'setup', 'validate',

    *vars(operator),
    'call', 'dict', 'weakref', 'repr', 'hash', 'str', 'getattribute', 'setattr', 'delattr',
    'init', 'new', 'reduceex', 'reduce', 'subclasshook', 'initsubclass', 'format', 'sizeof',
    'dir', 'class', 'doc', 'module', 'bytes', 'int', 'iter'
)

IGNORE_ATTRS = tuple(map(_dunder, STRIPPED_IGNORE_ATTRS))

C = TypeVar('C', bound=cs.Construct)


class _Missing:
    def __repr__(self):
        return 'Missing'


Missing = _Missing()

__registry = {
    'constructs': {},
    'factories': {},
    'aliased_args': {},
    'reserve_args': {},
    'field_subregistries': {},
}


def create_dict_registry(
        key: str,
        global_default: Any = Missing,
        create_if_missing=True,
        raise_for_missing=False,
        registry: Optional[MutableMapping] = None,
):
    if registry is None:
        registry = __registry

    def op_get(obj, default: Any = Missing, silent: bool = False):
        if default is Missing and global_default is not Missing:
            default = global_default
        raise_missing_here = raise_for_missing and not silent
        value = registry[key].get(id(obj), default)
        if create_if_missing and value is default:
            registry[key][id(obj)] = value
        if value is default and raise_missing_here:
            raise ValueError(f'value from {key} registry is missing')
        return value

    prefix = 'get_from_'
    op_get.__name__ = prefix + key

    def op_set(obj, value):
        registry[key][id(obj)] = value

    prefix = 'set_from_'
    op_get.__name__ = prefix + key

    return op_get, op_set


_get_factory, _set_factory = create_dict_registry('factories', raise_for_missing=True)
_get_construct, _set_construct = create_dict_registry('constructs', raise_for_missing=True)
_get_reserve_args, _set_reserve_args = create_dict_registry('reserve_args', global_default={})
_get_aliased_args, _set_aliased_args = create_dict_registry('aliased_args', global_default={})
_get_subregistry, _set_subregistry = create_dict_registry('field_subregistries', global_default={})


def _ensure_type(obj):
    if isinstance(obj, type):
        return obj
    return type(obj)


class FieldDescriptor(cs.Subconstruct):
    def __init__(self, subcon, name, default=Missing, validate=True):
        if not isinstance(subcon, cs.Construct):
            if isinstance(subcon, cs.bytestringtype):
                subcon = cs.Const(subcon)
            else:
                raise ValueError(
                    f'attempted to cast a non-construct field {name!r} to a constant field, '
                    'but it is not a byte string; consider using construct.Const '
                    'or construct.Default'
                )
        super().__init__(subcon)
        self.name = name
        self.default = default
        self.registry = {'bind': {}}
        (
            self._get,
            self._set
        ) = create_dict_registry('bind', registry=self.registry)
        self._validate = validate

    def validate(self, instance, value):
        if instance.__validate__ and self._validate:
            self.subcon.build(value)
        return value

    def get(self, instance):
        value = self._get(instance)
        if value is Missing:
            if isinstance(self.subcon, cs.Const):
                return self.subcon.value
            return self.default
        return value

    @classmethod
    def _map_field(cls, value, name):
        if not isinstance(value, cls):
            value = cls(value, name)
        return value

    def __get__(self, instance, owner):
        return self.get(instance)

    def __set__(self, instance, value):
        self._set(instance, self.validate(instance, value))

    def __truediv__(self, other):
        return cs.Renamed(self, other)

    __rtruediv__ = __truediv__


def _finalize_for_construct(obj, args=None, descriptor_class=FieldDescriptor):
    if args is None:
        args = _get_fields(obj)
    reserve_args = _get_reserve_args(obj)
    aliased_args = {}
    final_args = {}
    for name, attr in reserve_args.items():
        if name in args:
            aliased_arg = _get_alias(name)
            if aliased_arg in args:
                raise ValueError(f'cannot alias argument {name}: {aliased_arg} taken')
            aliased_args[aliased_arg] = name
            final_args[name] = args.pop(attr)
        else:
            arg = args.get(attr, Missing)
            if arg is not Missing:
                final_args[name] = arg
    _set_aliased_args(obj, aliased_args)
    for name, value in args.items():
        if name in IGNORE_ATTRS:
            continue
        set_name = name
        if name in aliased_args:
            set_name = _get_alias(name)
        final_args[set_name] = field = descriptor_class._map_field(value, name)
        setattr(obj, name, field)
        subregistry = _get_subregistry(obj)
        subregistry[name] = field
        _set_subregistry(obj, subregistry)
    return final_args


def _preprocess_construct(class_or_construct):
    pass


def _hook(class_):
    if not class_.__setup__:
        return
    _set_construct(class_, _get_factory(class_.mro()[1])(**_finalize_for_construct(class_)))


def _create_class(
        factory: Type[C],
        reserve_args: Sequence[str] = (),
        **custom_reserve_args: str
):
    reserve_args = {name: f'__{name.strip("_")}__' for name in reserve_args}
    for name, reserved_arg in custom_reserve_args.items():
        if name in reserve_args:
            raise ValueError(f'double-passed {name!r} in reserved args')
        reserve_args[name] = reserved_arg
    class_ = type(
        factory.__name__,
        (NetcastConstruct,),
        {'__init_subclass__': _hook}
    )
    _set_factory(class_, factory)
    _set_reserve_args(class_, reserve_args)
    return class_


def _create_subclass(class_, args, metaclass=type):
    subclass = metaclass(class_.__name__, (class_,), {'__setup__': False})
    _set_factory(subclass, _get_factory(class_))
    _set_construct(subclass, _get_factory(class_)(**_finalize_for_construct(class_, args=args)))
    return object.__new__(subclass)  # type: ignore


def _serialize_from_object(class_, obj, **context_kwds):
    fields = {**_get_fields(class_, final=True), **obj}
    obj = {
        key: value
        for key, value in fields.items()
        if value is not Missing
    }
    return _get_construct(class_).build(obj, **context_kwds)


def serialize(construct, **obj):
    return _serialize_from_object(construct, obj)


def reinterpret(class_, byte_string, **context_kwds):
    container = _get_construct(class_).parse(byte_string, **context_kwds)
    for key, val in container.items():
        setattr(class_, key, val)
    return class_


def _get_fields(construct, aliased_form=False, final=False):
    """"""
    if final:
        aliased_form = True
    subregistry = _get_subregistry(construct)
    if subregistry:
        data = dict(subregistry)
    else:
        data = construct if isinstance(construct, dict) else vars(construct)
    return {
        (
            _get_alias(key) if key in _get_aliased_args(construct) and aliased_form else key
        ):
            value.get(construct) if final else value
        for key, value in data.items()
        if key not in IGNORE_ATTRS
    }


def _get_alias(name):
    suffix = '_alias'
    return name + suffix


def _repr(obj):
    class_name = _ensure_type(obj).__name__
    fields = ', '.join(f'{k}={v!r}' for k, v in _get_fields(obj, final=True).items())
    repr_string = class_name + f'({fields})'
    if _ensure_type(obj).mro()[1] == NetcastConstruct:
        return repr_string.join('<>')
    return repr_string


class NetcastConstructMeta(type):
    __repr__ = _repr


class NetcastConstruct(metaclass=NetcastConstructMeta):
    __setup__ = True
    __validate__ = True

    def __new__(cls, **kwargs):
        if _get_construct(cls, silent=True) is Missing:
            return _create_subclass(cls, kwargs)
        elif kwargs:
            fields = _get_fields(cls)
            if not fields:
                return _create_subclass(cls, kwargs)
            self = object.__new__(cls)
            for key, val in kwargs.items():
                if key not in fields:
                    raise ValueError(f'unexpected argument: {key!r} (no such field)')
                setattr(self, key, val)
            return self
        return object.__new__(cls)

    def __call__(self, **kwargs):
        return self.__new__(type(self), **kwargs)

    def __bytes__(self):
        return serialize(self)

    __repr__ = _repr


Struct = _create_class(cs.Struct)
Sequence = _create_class(cs.Sequence)
FocusedSeq = _create_class(cs.FocusedSeq, reserve_args=['parsebuildfrom'])
Union = _create_class(cs.Union, reserve_args=['parsefrom'])
Select = _create_class(cs.Select)
LazyStruct = _create_class(cs.LazyStruct)
