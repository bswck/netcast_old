import functools
import operator
from typing import Type, TypeVar, Sequence, Any

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


M = _Missing()

__registry = {
    'constructs': {},
    'factories': {},
    'aliased_args': {},
    'reserve_args': {},
    'field_subregs': {},
}


def create_dict_registry(
        key,
        default: Any = M,
        create_if_missing=True,
        raise_for_missing=False,
        registry=None
):
    if registry is None:
        registry = __registry

    prefix = 'get_from_'

    @functools.wraps(prefix + key)
    def op_get(obj, quiet_if_missing=False):
        raise_missing_here = raise_for_missing and not quiet_if_missing
        value = registry[key].get(id(obj), default)
        if create_if_missing and value is default:
            registry[key][id(obj)] = value
        if value is default and raise_missing_here:
            raise ValueError(f'value from {key} registry is missing')
        return value

    prefix = 'set_from_'

    @functools.wraps(prefix + key)
    def op_set(obj, value):
        registry[key][id(obj)] = value

    return op_get, op_set


get_factory, set_factory = create_dict_registry('factories', raise_for_missing=True)
get_construct, set_construct = create_dict_registry('constructs', raise_for_missing=True)
get_reserve_args, set_reserve_args = create_dict_registry('reserve_args', default={})
get_aliased_args, set_aliased_args = create_dict_registry('aliased_args', default={})
get_subreg, set_subreg = create_dict_registry('field_subregs', default={})


def ensure_type(obj):
    if isinstance(obj, type):
        return obj
    return type(obj)


def finalize_args(cls, args=None):
    if args is None:
        args = get_fields(cls)
    reserve_args = get_reserve_args(cls)
    aliased_args = {}
    final_args = {}
    for name, attr in reserve_args.items():
        if name in args:
            aliased_arg = get_alias(name)
            if aliased_arg in args:
                raise ValueError(f'cannot alias argument {name}: {aliased_arg} taken')
            aliased_args[aliased_arg] = name
            final_args[name] = args.pop(attr)
        else:
            arg = args.get(attr, M)
            if arg is not M:
                final_args[name] = arg
    set_aliased_args(cls, aliased_args)
    for name, value in args.items():
        if name in IGNORE_ATTRS:
            continue
        set_name = name
        if name in aliased_args:
            set_name = get_alias(name)
        final_args[set_name] = field = wrap_field(value, name)
        setattr(cls, name, field)
        field_subreg = get_subreg(cls)
        field_subreg[name] = field
        set_subreg(cls, field_subreg)
    return final_args


def hook(cls):
    cls.__setup__ and set_construct(cls, get_factory(cls.mro()[1])(**finalize_args(cls)))


def create_subclass(class_, args):
    subcls = type(class_.__name__, (class_,), {'__setup__': False})
    set_factory(subcls, get_factory(class_))
    set_construct(subcls, get_factory(class_)(**finalize_args(class_, args=args)))
    return object.__new__(subcls)  # type: ignore


def serialize_from_object(class_, obj, **context_kwds):
    fields = {**get_fields(class_, final=True), **obj}
    obj = {
        key: value
        for key, value in fields.items()
        if value is not M
    }
    return get_construct(ensure_type(class_)).build(obj, **context_kwds)


def serialize(decl, **obj):
    return serialize_from_object(decl, obj)


def reinterpret(class_, byte_string, **context_kwds):
    container = get_construct(ensure_type(class_)).parse(byte_string, **context_kwds)
    for key, val in container.items():
        setattr(class_, key, val)
    return class_


def create_class(
        factory: Type[C],
        reserve_args: Sequence[str] = (),
        **custom_reserve_args: str
):
    reserve_args = {name: f'__{name}__' for name in reserve_args}
    for name, reserved_arg in custom_reserve_args.items():
        if name in reserve_args:
            raise ValueError(f'double-passed {name!r} in reserved args')
        reserve_args[name] = reserved_arg
    class_ = type(
        factory.__name__,
        (DeclarativeConstruct,),
        {'__init_subclass__': hook}
    )
    set_factory(class_, factory)
    set_reserve_args(class_, reserve_args)
    return class_


def get_fields(class_, aliased_form=False, final=False):
    if final:
        aliased_form = True
    subreg = get_subreg(class_)
    if subreg:
        data = dict(subreg)
    else:
        data = class_ if isinstance(class_, dict) else vars(class_)
    return {
        (
            get_alias(key) if key in get_aliased_args(class_) and aliased_form else key
        ):
            value.get(class_) if final else value
        for key, value in data.items()
        if key not in IGNORE_ATTRS
    }


def wrap_field(value, name):
    if not isinstance(value, FieldDescriptor):
        value = FieldDescriptor(value, name)
    return value


def get_alias(name):
    return name + '_alias'


class FieldDescriptor(cs.Subconstruct):
    def __init__(self, subcon, name, default=M, validate=True):
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
        if value is M:
            if isinstance(self.subcon, cs.Const):
                return self.subcon.value
            return self.default
        return value

    def __get__(self, instance, owner):
        return self.get(instance)

    def __set__(self, instance, value):
        self._set(instance, self.validate(instance, value))

    def __truediv__(self, other):
        return cs.Renamed(self, other)

    __rtruediv__ = __truediv__


class DeclarativeConstructMeta(type):
    def __repr__(self):
        class_name = self.__name__
        fields_format = ', '.join(f'{k}={v!r}' for k, v in get_fields(self, final=True).items())
        repr_string = class_name + f'({fields_format})'
        if self.mro()[1] == DeclarativeConstruct:
            return repr_string.join('<>')
        return repr_string


class DeclarativeConstruct(metaclass=DeclarativeConstructMeta):
    __setup__ = True
    __validate__ = True

    def __new__(cls, **kwargs):
        if get_construct(cls, quiet_if_missing=True) is M:
            return create_subclass(cls, kwargs)
        elif kwargs:
            fields = get_fields(cls)
            if not fields:
                return create_subclass(cls, kwargs)
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

    def __repr__(self):
        class_name = type(self).__name__
        fields_fmt = ', '.join(f'{k}={v!r}' for k, v in get_fields(self, final=True).items())
        repr_string = class_name + f'({fields_fmt})'
        if type(self).mro()[1] == DeclarativeConstruct:
            return repr_string.join('<>')
        return repr_string


Struct = create_class(cs.Struct)
Sequence = create_class(cs.Sequence)
FocusedSeq = create_class(cs.FocusedSeq, reserve_args=['parsebuildfrom'])
Union = create_class(cs.Union, reserve_args=['parsefrom'])
Select = create_class(cs.Select)
LazyStruct = create_class(cs.LazyStruct)
