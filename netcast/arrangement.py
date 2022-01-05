from __future__ import annotations

import functools
import operator
import threading
from typing import Any, ClassVar, Type

from netcast.context import (
    Context,
    _LocalHook,
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
    BytesIOContext,
    StringIOContext,
    FileIOContext
)
from netcast.toolkit.collections import MemoryDict, Params


CAT, AT = Type["ClassArrangement"], Type["Arrangement"]


def _arrangement_init(self, descent=None):
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
            cls,
            descent=None,
            clear_init=False,
            context_class=None,
            abstract=False,
            netcast=False,
            _use_wrapper=True,
            _type_check=True
    ):
        """When a new subclass is created, handle its access to the local context."""
        if getattr(cls, '_context_lock', None) is None:
            cls._context_lock = threading.RLock()

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

        if _use_wrapper and not _LocalHook.is_prepared(context):
            context = cls.get_context()
            context_wrapper = cls.context_wrapper
            if not _is_classmethod(cls, cls.context_wrapper):
                context_wrapper = functools.partial(context_wrapper, cls)
            cls._context = next(context_wrapper(context), context)

        if clear_init:
            cls.__init__ = _arrangement_init

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context()

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext()

    @property
    def inherits_context(self) -> bool:
        return self.inherit_context


class Arrangement(ClassArrangement, netcast=True):
    descent: Arrangement | None
    _inherits_context = True

    def __init__(self, descent=None):
        _arrangement_init(self, descent)

    def __init_subclass__(
            cls,
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

        fixed_type = getattr(cls, 'descent_type', None)
        if None not in (descent, fixed_type):
            if not isinstance(descent, fixed_type):  # soft-check descent type
                raise TypeError(
                    'passed descent\'s type '
                    'and the fixed descent type are not equal'
                )

        contexts = cls.get_context()
        self = object.__new__(cls)
        _arrangement_init(self, descent)
        if contexts is None:
            raise TypeError('abstract class')
        if inherit_context and descent is not None:
            context = contexts.get(descent)
            if context is None:
                context = descent.get_context()[descent]
            contexts[self] = context
        elif descent is not None:
            contexts[self] = cls._create_context(contexts[descent], self=self)
        else:
            contexts[self] = cls._create_context(self=self)
        context = contexts[self]
        with self._context_lock:
            unprepared = _LocalHook.is_prepared(context)
            if unprepared:
                context_wrapper = cls.context_wrapper
                if _is_classmethod(cls, context_wrapper) or isinstance(context_wrapper, staticmethod):
                    context_wrapper = functools.partial(context_wrapper)
                else:
                    context_wrapper = functools.partial(context_wrapper, self)
                contexts[self] = next(context_wrapper(context), context)
                _LocalHook.on_prepare(context)
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


def wrap_to_arrangement(name, context_class, class_arrangement=False, doc=None, env=None):
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement
    if env is None:
        env = {}
    cls = type(name, (super_class,), env, abstract=True, context_class=context_class)
    if doc:
        cls.__doc__ = doc
    return cls


ClassDictArrangement = wrap_to_arrangement('ClassDictArrangement', DictContext, True)
ClassListArrangement = wrap_to_arrangement('ClassListArrangement', ListContext, True)
ClassByteArrayArrangement = wrap_to_arrangement('ClassByteArrayArrangement', ByteArrayContext, True)
ClassDequeArrangement = wrap_to_arrangement('ClassDequeArrangement', DequeContext, True)
ClassQueueArrangement = wrap_to_arrangement('ClassQueueArrangement', QueueContext, True)
ClassLifoQueueArrangement = wrap_to_arrangement('ClassLifoQueueArrangement', LifoQueueContext, True)
ClassPriorityQueueArrangement = wrap_to_arrangement('ClassPriorityQueueArrangement', PriorityQueueContext, True)  # noqa: E501
ClassAsyncioQueueArrangement = wrap_to_arrangement('ClassAsyncioQueueArrangement', AsyncioQueueContext, True)  # noqa: E501
ClassAsyncioLifoQueueArrangement = wrap_to_arrangement('ClassAsyncioLifoQueueArrangement', AsyncioLifoQueueContext, True)  # noqa: E501
ClassAsyncioPriorityQueueArrangement = wrap_to_arrangement('ClassAsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext, True)  # noqa: E501
ClassBytesIOArrangement = wrap_to_arrangement('ClassBytesIOArrangement', BytesIOContext, True)
ClassStringIOArrangement = wrap_to_arrangement('ClassStringIOArrangement', StringIOContext, True)
ClassFileIOArrangement = wrap_to_arrangement('ClassFileIOArrangement', FileIOContext, True)

DictArrangement = wrap_to_arrangement('DictArrangement', DictContext)
ListArrangement = wrap_to_arrangement('ListArrangement', ListContext)
ByteArrayArrangement = wrap_to_arrangement('ByteArrayArrangement', ByteArrayContext)
DequeArrangement = wrap_to_arrangement('DequeArrangement', DequeContext)
QueueArrangement = wrap_to_arrangement('QueueArrangement', QueueContext)
LifoQueueArrangement = wrap_to_arrangement('LifoQueueArrangement', LifoQueueContext)
PriorityQueueArrangement = wrap_to_arrangement('PriorityQueueArrangement', PriorityQueueContext)
AsyncioQueueArrangement = wrap_to_arrangement('AsyncioQueueArrangement', AsyncioQueueContext)
AsyncioLifoQueueArrangement = wrap_to_arrangement('AsyncioLifoQueueArrangement', AsyncioLifoQueueContext)  # noqa: E501
AsyncioPriorityQueueArrangement = wrap_to_arrangement('AsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext)  # noqa: E501
FileIOArrangement = wrap_to_arrangement('FileIOArrangement', FileIOContext)
BytesIOArrangement = wrap_to_arrangement('BytesIOArrangement', BytesIOContext)
StringIOArrangement = wrap_to_arrangement('StringIOArrangement', StringIOContext)

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
BIOArrangement = BytesIOArrangement
SIOArrangement = StringIOArrangement
