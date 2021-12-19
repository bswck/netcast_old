from __future__ import annotations

from typing import Any, ClassVar, Type

from netcast.context import (
    Context, DictContext, ListContext, DequeContext, QueueContext,
    LifoQueueContext, PriorityQueueContext, AsyncioQueueContext,
    AsyncioLifoQueueContext, AsyncioPriorityQueueContext, MemoryDictContext
)
from netcast.toolkit.collections import MemoryDict


def _init_arrangement(self, descent=None):
    self.descent = descent


class _BaseArrangement:
    _super_registry = MemoryDict()  # B-)
    """Helper dict for managing an arrangement's class attributes."""

    context_class: ClassVar[Type[Context] | None] = None
    """Context class. Must derive from the abstract class :class:`Context`."""

    _cls_context: Context | Any | None
    """A :class:`Context` object shared across members of a class arrangement."""

    inherit_context: bool | None = None
    """
    Indicates whether to inherit the context directly from the superclass
    or create a new context for this class and mark the upper as a supercontext.

    Defaults to True.
    """

    @classmethod
    def _get_supercontext(cls):
        return _BaseArrangement._super_registry.get(cls._get_context())

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
    def _get_context(cls, *args, **kwargs):
        """Get the current context."""
        return getattr(cls, '_cls_context', None)


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
    Instances that participate in an instance arrangement must be given an descent they work with.
    """

    @classmethod
    def _get_inherit_context(cls):
        if cls.inherit_context is None:
            return True
        return cls.inherit_context

    @classmethod
    def _get_context_class(cls, context_class=None):
        if (context_class, cls.context_class) == (None, None):
            context_class = DictContext
        elif None not in (context_class, cls.context_class):
            raise ValueError('context_class= set both when subclassing and in a subclass')
        else:
            context_class, = filter(None, (context_class, cls.context_class))
        cls.context_class = context_class
        return context_class

    def __init_subclass__(
            cls, *,
            descent=None,
            clear_init=False,
            context_class=None,
            toplevel=False,
            netcast=False
    ):
        """When a new subclass is created, handle its access to the local context."""
        if netcast:
            return

        inherit_context = cls._get_inherit_context()
        context_class = cls._get_context_class(context_class)
        assert issubclass(context_class, Context)

        if toplevel:
            cls.inherit_context = None
            return

        if descent is None:
            descent = super(ClassArrangement, cls)
        else:
            cls._known_descent_type = descent

        context = descent._get_context()
        null_context = context is None

        if null_context:
            context = cls._create_context()

        if inherit_context or null_context:
            cls._cls_context = context
        else:
            cls._cls_context = cls._create_context(context)

        cls.inherit_context = None

        if clear_init:
            cls.__init__ = _init_arrangement

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self._get_context()

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext()


class Arrangement(ClassArrangement, netcast=True):
    __init__ = _init_arrangement

    def __init_subclass__(
            cls, *,
            descent=None,
            clear_init=False,
            context_class=None,
            toplevel=False,
            netcast=False
    ):
        if netcast:
            return

        context_class = cls._get_context_class(context_class)
        inherit_context = cls._get_inherit_context()
        cls.context_class = None
        cls.inherit_context = True
        super().__init_subclass__(
            descent=descent, clear_init=clear_init,
            context_class=MemoryDictContext, toplevel=toplevel, netcast=netcast
        )
        cls.context_class = context_class
        if netcast:
            return
        cls.inherit_context = inherit_context

    def __new__(cls, *args, **kwargs):
        if args:
            descent, *args = args
        else:
            descent = None
        inherit_context = cls.inherit_context

        fixed_descent_type = getattr(cls, '_fixed_descent_type', None)
        if fixed_descent_type is not None:
            if not isinstance(descent, fixed_descent_type):  # soft-check descent type
                raise TypeError('passed descent\'s type and the fixed descent type are not alike')

        contexts = cls._get_context()
        self = object.__new__(cls)

        if inherit_context and descent is not None:
            contexts[self] = contexts[descent]
        elif descent is not None:
            contexts[self] = cls._create_context(contexts[descent])
        else:
            contexts[self] = cls._create_context()
        return self

    @classmethod
    def _get_context(cls, self=None):
        """Get the current context."""
        contexts = super()._get_context()
        if self is None:
            return contexts
        return contexts[self]

    @classmethod
    def _get_supercontext(cls, self=None):
        """Get the current supercontext."""
        if self is None:
            return super()._get_supercontext()
        return _BaseArrangement._super_registry.get(cls._get_context(self))

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self._get_context(self)

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext(self)


def _arrangement(name, context_class, class_arrangement=False, doc=None):
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement

    class _BoilerplateArrangement(super_class, context_class=context_class, toplevel=True):
        __name__ = name
        __doc__ = doc

    return _BoilerplateArrangement


ClassDictArrangement = _arrangement('ClassDictArrangement', DictContext, True)
ClassListArrangement = _arrangement('ClassListArrangement', ListContext, True)
ClassDequeArrangement = _arrangement('ClassDequeArrangement', DequeContext, True)

ClassQueueArrangement = _arrangement('ClassQueueArrangement', QueueContext, True)
ClassLifoQueueArrangement = _arrangement('ClassLifoQueueArrangement', LifoQueueContext, True)
ClassPriorityQueueArrangement = _arrangement('ClassPriorityQueueArrangement', PriorityQueueContext, True)  # noqa: E501

ClassAsyncioQueueArrangement = _arrangement('ClassAsyncioQueueArrangement', AsyncioQueueContext, True)  # noqa: E501
ClassAsyncioLifoQueueArrangement = _arrangement('ClassAsyncioQueueArrangement', AsyncioLifoQueueContext, True)  # noqa: E501
ClassAsyncioPriorityQueueArrangement = _arrangement('ClassPriorityQueueArrangement', AsyncioPriorityQueueContext, True)  # noqa: E501

DictArrangement = _arrangement('DictArrangement', DictContext)
ListArrangement = _arrangement('ListArrangement', ListContext)
DequeArrangement = _arrangement('DequeArrangement', DequeContext)

QueueArrangement = _arrangement('QueueArrangement', QueueContext)
LifoQueueArrangement = _arrangement('LifoQueueArrangement', LifoQueueContext)
PriorityQueueArrangement = _arrangement('PriorityQueueArrangement', PriorityQueueContext)

AsyncioQueueArrangement = _arrangement('AsyncioQueueArrangement', AsyncioQueueContext)
AsyncioLifoQueueArrangement = _arrangement('AsyncioQueueArrangement', AsyncioLifoQueueContext)
AsyncioPriorityQueueArrangement = _arrangement('AsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext)  # noqa: E501
