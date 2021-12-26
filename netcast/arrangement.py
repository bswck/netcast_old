from __future__ import annotations

import functools
import operator
from typing import Any, ClassVar, Type

from netcast.context import (
    Context,
    ContextHook,
    ListContext,
    DequeContext,
    DictContext,
    ByteArrayContext,
    MemoryDictContext,
    QueueContext,
    PriorityQueueContext,
    LifoQueueContext,
    AsyncioQueueContext,
    AsyncioPriorityQueueContext,
    AsyncioLifoQueueContext,
    FileIOContext,
    BytesIOContext,
    StringIOContext,
)
from netcast.toolkit.collections import MemoryDict, Params


CAT, AT = Type["ClassArrangement"], Type["Arrangement"]


def _init_arrangement(self, descent=None):
    self.descent = descent


def _is_classmethod(cls, method):
    return getattr(method, '__self__', None) is cls


DEFAULT_CONTEXT_CLASS = DictContext


class _BaseArrangement:
    _super_registry = MemoryDict()  # B-)
    """Helper dict for managing an arrangement's class attributes."""

    context_class: ClassVar[Type[Context] | None] = None
    """Context class. Must derive from the abstract class :class:`Context`."""

    _context: Context | Any | None
    """A :class:`Context` object shared across members of a class arrangement."""

    inherit_context: bool | None = None
    """
    Indicates whether to inherit the context directly from the superclass
    or create a new context for this class and mark the upper as a supercontext.

    Defaults to True.
    """
    context_params = Params()

    @classmethod
    def _get_supercontext(cls):
        return _BaseArrangement._super_registry.get(cls.get_context())

    @staticmethod
    def _set_supercontext(context: Context, supercontext: Context | None):
        _BaseArrangement._super_registry[context] = supercontext

    @classmethod
    def _create_context(cls, supercontext=None, context_class=None, self=None) -> Any:
        """Create a new context associated with its descent, :param:`supercontext`."""
        if context_class is None:
            context_class = cls.context_class
        args, kwargs = cls.context_params
        cls_or_self = cls if self is None else self
        if callable(args):
            args = args(cls_or_self)
        if callable(kwargs):
            kwargs = kwargs(cls_or_self)
        context = context_class(*args, **kwargs)
        cls._set_supercontext(context, supercontext)
        return context

    @classmethod
    def get_context(cls, *args, **kwargs):
        """Get the current context."""
        return getattr(cls, '_context', None)


class ClassArrangement(_BaseArrangement):
    """
    An arrangement of classes bound to a :class:`Context` object.

    When :class:`ClassArrangement` is subclassed, that subclass enters a new context.
    All its subclasses then may inherit it and then modify this context.

    When :class:`ClassArrangement` subclass' subclass has set `inherit_context` to False,
    then a new context is bound to it. The last subclass accesses the top-level context using
    `supercontext` property and the further subclasses access one context further so on.

    Note that it might be especially useful if those classes are singletons,
    however you may use :class:`Arrangement` for instance-context arrangements.
    Instances that participate in an instance arrangement must be given their descent.
    """
    descent_type: Type[ClassArrangement] | None
    _default_context_class = True

    @classmethod
    def context_wrapper(cls, context):
        yield context

    @classmethod
    def _get_inherit_context(cls):
        if cls.inherit_context is None:
            return True
        return cls.inherit_context

    @classmethod
    def _get_context_class(cls, context_class=None, inherit_context=None, descent=None):
        args = (context_class, cls.context_class)
        if None not in args and operator.is_not(*args):
            raise ValueError('context_class= set both when subclassing and in a subclass')
        descent_context_class = getattr(descent, 'context_class', context_class)
        if any(args):
            context_class, = filter(None, args)
        if context_class is None and descent_context_class is None:
            context_class = DEFAULT_CONTEXT_CLASS
        _original_context_class: type | None = context_class
        if context_class is None:
            context_class = descent_context_class
            cls._default_context_class = False
        if (
                descent is not None
                and inherit_context is not None
                and inherit_context
                and None not in (_original_context_class, descent_context_class)
        ):
            _original_context_class: type
            descent_context_class: type
            if not issubclass(_original_context_class, descent_context_class):
                raise TypeError(
                    'context_class is different for descent and this class '
                    '(inherit_context = False may fix this error)'
                )
        cls.context_class = context_class
        return context_class

    def __init_subclass__(
            cls, *,
            descent=None,
            clear_init=False,
            context_class=None,
            abstract=False,
            netcast=False,
            _use_wrapper=True,
            _type_check=True
    ):
        """When a new subclass is created, handle its access to the local context."""
        if netcast:
            return

        if descent is None:
            descent = cls.__base__

        cls.descent_type = descent

        inherit_context = cls._get_inherit_context()
        if _type_check:
            context_class = cls._get_context_class(
                context_class,
                inherit_context and not abstract,
                descent
            )
        else:
            context_class = cls._get_context_class(context_class)
        assert issubclass(context_class, Context)

        if abstract:
            cls.inherit_context = None
            return

        context = descent.get_context()
        null_context = context is None

        if null_context:
            context = cls._create_context()

        if inherit_context or null_context:
            cls._context = context
        else:
            cls._context = cls._create_context(context)

        cls.inherit_context = None

        if _use_wrapper and not ContextHook.is_prepared(context):
            context = cls.get_context()
            context_wrapper = cls.context_wrapper
            if not _is_classmethod(cls, cls.context_wrapper):
                context_wrapper = functools.partial(context_wrapper, cls)
            cls._context = next(context_wrapper(context), context)

        if clear_init:
            cls.__init__ = _init_arrangement

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context()

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext()


class Arrangement(ClassArrangement, netcast=True):
    descent: Arrangement | None
    _inherits_context = True

    def __init__(self, descent=None):
        _init_arrangement(self, descent)

    def __init_subclass__(
            cls, *,
            descent=None,
            clear_init=False,
            context_class=None,
            abstract=False,
            netcast=False,
            **kwargs
    ):
        if netcast:
            return
        context_class = cls._get_context_class(context_class)
        inherit_context = cls._get_inherit_context()
        cls.context_class = None
        cls.inherit_context = True
        super().__init_subclass__(
            descent=descent, clear_init=clear_init,
            context_class=MemoryDictContext, abstract=abstract, netcast=netcast,
            _use_wrapper=False, _type_check=False
        )
        cls.context_class = context_class
        if netcast:
            return
        cls._inherits_context = inherit_context

    def __new__(cls, *args, **kwargs):
        if args:
            descent, *args = args
        else:
            descent = None
        inherit_context = cls._inherits_context

        fixed_descent_type = getattr(cls, 'descent_type', None)
        if None not in (descent, fixed_descent_type):
            if not isinstance(descent, fixed_descent_type):  # soft-check descent type
                raise TypeError('passed descent\'s type and the fixed descent type are not alike')

        contexts = cls.get_context()
        self = object.__new__(cls)
        self.descent = descent
        if contexts is None:
            raise TypeError('abstract class')
        if inherit_context and descent is not None:
            contexts[self] = contexts[descent]
        elif descent is not None:
            contexts[self] = cls._create_context(contexts[descent], self=self)
        else:
            contexts[self] = cls._create_context(self=self)
        context = contexts[self]
        if not ContextHook.is_prepared(context):
            context_wrapper = cls.context_wrapper
            if _is_classmethod(cls, context_wrapper) or isinstance(context_wrapper, staticmethod):
                context_wrapper = functools.partial(context_wrapper)
            else:
                context_wrapper = functools.partial(context_wrapper, self)
            contexts[self] = next(context_wrapper(context), context)
            ContextHook.on_prepare(context)
        return self

    def context_wrapper(self, context):
        yield context

    @classmethod
    def get_context(cls, self=None):
        """Get the current context."""
        contexts = super().get_context()
        if self is None:
            return contexts
        return contexts[self]

    @classmethod
    def _get_supercontext(cls, self=None):
        """Get the current supercontext."""
        if self is None:
            return super()._get_supercontext()
        return _BaseArrangement._super_registry.get(cls.get_context(self))

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context(self)

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext(self)

    @property
    def inherits_context(self) -> bool:
        return self._inherits_context


def _wrap_arrangement(name, context_class, class_arrangement=False, doc=None, env=None):
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement
    if env is None:
        env = {}
    _BoilerplateArrangement = type(name, (super_class,), env, abstract=True, context_class=context_class)
    if doc:
        _BoilerplateArrangement.__doc__ = doc
    return _BoilerplateArrangement


ClassDictArrangement = _wrap_arrangement('ClassDictArrangement', DictContext, True)
ClassListArrangement = _wrap_arrangement('ClassListArrangement', ListContext, True)
ClassByteArrayArrangement = _wrap_arrangement('ClassByteArrayArrangement', ByteArrayContext, True)
ClassDequeArrangement = _wrap_arrangement('ClassDequeArrangement', DequeContext, True)
ClassQueueArrangement = _wrap_arrangement('ClassQueueArrangement', QueueContext, True)
ClassLifoQueueArrangement = _wrap_arrangement('ClassLifoQueueArrangement', LifoQueueContext, True)
ClassPriorityQueueArrangement = _wrap_arrangement('ClassPriorityQueueArrangement', PriorityQueueContext, True)  # noqa: E501
ClassAsyncioQueueArrangement = _wrap_arrangement('ClassAsyncioQueueArrangement', AsyncioQueueContext, True)  # noqa: E501
ClassAsyncioLifoQueueArrangement = _wrap_arrangement('ClassAsyncioLifoQueueArrangement', AsyncioLifoQueueContext, True)  # noqa: E501
ClassAsyncioPriorityQueueArrangement = _wrap_arrangement('ClassAsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext, True)  # noqa: E501
# ClassFileIOArrangement = _wrap_arrangement('ClassFileIOArrangement', FileIOContext)
ClassBytesIOArrangement = _wrap_arrangement('ClassBytesIOArrangement', BytesIOContext)
ClassStringIOArrangement = _wrap_arrangement('ClassStringIOArrangement', StringIOContext)

DictArrangement = _wrap_arrangement('DictArrangement', DictContext)
ListArrangement = _wrap_arrangement('ListArrangement', ListContext)
ByteArrayArrangement = _wrap_arrangement('ByteArrayArrangement', ByteArrayContext)
DequeArrangement = _wrap_arrangement('DequeArrangement', DequeContext)
QueueArrangement = _wrap_arrangement('QueueArrangement', QueueContext)
LifoQueueArrangement = _wrap_arrangement('LifoQueueArrangement', LifoQueueContext)
PriorityQueueArrangement = _wrap_arrangement('PriorityQueueArrangement', PriorityQueueContext)
AsyncioQueueArrangement = _wrap_arrangement('AsyncioQueueArrangement', AsyncioQueueContext)
AsyncioLifoQueueArrangement = _wrap_arrangement('AsyncioLifoQueueArrangement', AsyncioLifoQueueContext)  # noqa: E501
AsyncioPriorityQueueArrangement = _wrap_arrangement('AsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext)  # noqa: E501
# FileIOArrangement = _wrap_arrangement('FileIOArrangement', FileIOContext)
BytesIOArrangement = _wrap_arrangement('BytesIOArrangement', BytesIOContext)
StringIOArrangement = _wrap_arrangement('StringIOArrangement', StringIOContext)

# shortcuts
CArrangement = ClassArrangement
CDArrangement = ClassDictArrangement
CBAArrangement = CByteArrangement = ClassByteArrayArrangement
CLArrangement = ClassListArrangement
CDQArrangement = ClassDequeArrangement
CQArrangement = ClassQueueArrangement
CLQArrangement = ClassLifoQueueArrangement
CPQArrangement = ClassPriorityQueueArrangement
CAQArrangement = ClassAsyncioQueueArrangement
CALQArrangement = ClassAsyncioLifoQueueArrangement
CAPQArrangement = ClassAsyncioPriorityQueueArrangement
DArrangement = DictArrangement
LArrangement = ListArrangement
BAArrangement = ByteArrangement = ByteArrayArrangement
DQArrangement = DequeArrangement
QArrangement = QueueArrangement
LQArrangement = LifoQueueArrangement
PQArrangement = PriorityQueueArrangement
AQArrangement = AsyncioQueueArrangement
ALQArrangement = AsyncioLifoQueueContext
APQArrangement = AsyncioPriorityQueueContext
