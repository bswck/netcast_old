from __future__ import annotations

import functools
import operator
from typing import Any, ClassVar, Type

from netcast.context import (
    Context, DictContext, ListContext, DequeContext, QueueContext,
    LifoQueueContext, PriorityQueueContext, AsyncioQueueContext,
    AsyncioLifoQueueContext, AsyncioPriorityQueueContext, MemoryDictContext, ContextHook
)
from netcast.toolkit.collections import MemoryDict


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

    @classmethod
    def _get_supercontext(cls):
        return _BaseArrangement._super_registry.get(cls.get_context())

    @staticmethod
    def _set_supercontext(context: Context, supercontext: Context | None):
        _BaseArrangement._super_registry[context] = supercontext

    @classmethod
    def _create_context(cls, supercontext=None, context_class=None) -> Any:
        """Create a new context associated with its descent, :param:`supercontext`."""
        if context_class is None:
            context_class = cls.context_class
        context = context_class()
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
            descent = super(ClassArrangement, cls)
            cls.descent_type = None
        else:
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
        if fixed_descent_type is not None:
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
            contexts[self] = cls._create_context(contexts[descent])
        else:
            contexts[self] = cls._create_context()
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


def _ac(name, context_class, class_arrangement=False, doc=None):
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement

    class _Meta(type):
        def __repr__(self):
            return _BoilerplateArrangement.__module__ + '.' + name

    class _BoilerplateArrangement(
        super_class,
        context_class=context_class,
        abstract=True,
        metaclass=_Meta
    ):
        pass

    _BoilerplateArrangement.__name__ = name
    if doc:
        _BoilerplateArrangement.__doc__ = doc
    return _BoilerplateArrangement


ClassDictArrangement = _ac('ClassDictArrangement', DictContext, True)
ClassListArrangement = _ac('ClassListArrangement', ListContext, True)
ClassDequeArrangement = _ac('ClassDequeArrangement', DequeContext, True)

ClassQueueArrangement = _ac('ClassQueueArrangement', QueueContext, True)
ClassLifoQueueArrangement = _ac('ClassLifoQueueArrangement', LifoQueueContext, True)
ClassPriorityQueueArrangement = _ac('ClassPriorityQueueArrangement', PriorityQueueContext, True)

ClassAsyncioQueueArrangement = _ac('ClassAsyncioQueueArrangement', AsyncioQueueContext, True)
ClassAsyncioLifoQueueArrangement = _ac('ClassAsyncioLifoQueueArrangement', AsyncioLifoQueueContext, True)  # noqa: E501
ClassAsyncioPriorityQueueArrangement = _ac('ClassAsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext, True)  # noqa: E501

DictArrangement = _ac('DictArrangement', DictContext)
ListArrangement = _ac('ListArrangement', ListContext)
DequeArrangement = _ac('DequeArrangement', DequeContext)

QueueArrangement = _ac('QueueArrangement', QueueContext)
LifoQueueArrangement = _ac('LifoQueueArrangement', LifoQueueContext)
PriorityQueueArrangement = _ac('PriorityQueueArrangement', PriorityQueueContext)

AsyncioQueueArrangement = _ac('AsyncioQueueArrangement', AsyncioQueueContext)
AsyncioLifoQueueArrangement = _ac('AsyncioLifoQueueArrangement', AsyncioLifoQueueContext)
AsyncioPriorityQueueArrangement = _ac('AsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext)  # noqa: E501
