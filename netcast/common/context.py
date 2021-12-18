from __future__ import annotations

import enum
import functools

from traitlets import Bunch

_context_hooks = {}


class Context(Bunch):
    """
    A common context of associated classes or instances. Subclasses `traitlets.Bunch`.
    """

    def __setitem__(self, key, value):
        old_value = self.get(key)
        super().__setitem__(key, value)
        new_value = value
        _call_context_hooks(self, key, old_value, new_value)


def _init_arrangement(self, parent=None):
    self.parent = parent


def _call_context_hooks(context, key, old_value, new_value):
    all_hooks = _context_hooks.get(id(context), {})
    key_specific_hooks = all_hooks.get(key, [])
    generic_hooks = all_hooks.get(Missing, [])
    for hook in key_specific_hooks:
        hook(old_value, new_value)
    for hook in generic_hooks:
        hook(key, old_value, new_value)


Missing = object()  # TODO: make a nice symbol system or sth


def on_context_update(fn=None, *, class_=None, key=Missing):
    if fn is None:
        if class_ is None:
            raise ValueError('context family member class was not provided')
        return functools.partial(on_context_update, key=key)
    class_context = not isinstance(class_, Arrangement)
    if key is Missing:  # generic hook registration
        if class_context:
            _context_hooks[class_]  # noqa, WIP


_read_only_error = ValueError('context in this class is declared read-only')


class _ReadOnlyContextWrapper(Context):
    def __setitem__(self, key, value):
        raise _read_only_error

    def update(self, *args, **kwargs):
        raise _read_only_error

    def __delitem__(self, key):
        raise _read_only_error

    def __ior__(self, other):
        raise _read_only_error


class ReadOnlyLevel(enum.IntFlag):
    none = 1 << 0
    context = local_context = 1 << 1
    super_context = 1 << 2


class _BaseArrangement:
    _preloaded_hooks = {}

    _class_super_registry = {}  # B-)
    """Helper dict for managing :class:`ReceiveHandler` context class attributes."""

    _instance_super_registry = {}  # @.@
    """Helper dict for managing :class:`ReceiveHandler` context instance attributes."""

    _context: Context | None = Context()
    """
    A context class, instantiated during construction and then shared across sub-handlers.
    """

    inherit_context: bool | None = None
    """
    Indicates whether to create a new sub-context for the given class 
    (with the possibility of modifying the super-context) 
    or inherit it directly from the superclass.
    
    Defaults to True.
    """

    read_only_context: ReadOnlyLevel = ReadOnlyLevel.none
    # uhm… docs?

    @staticmethod
    def _get_super_context(context: Context):
        return _BaseArrangement._class_super_registry.get(id(context), None)

    @staticmethod
    def _set_super_context(context: Context, super_context: Context | None):
        _BaseArrangement._class_super_registry[id(context)] = super_context

    @classmethod
    def _create_context(cls, super_context=None):
        """Create a new context associated with its origin, :param:`super_context`."""
        context = Context()
        cls._set_super_context(context, super_context)
        return context

    @classmethod
    def _get_context(cls, *args, **kwargs):
        """Get the current context."""
        return cls._context


class ClassArrangement(_BaseArrangement):
    """
    A class bound to a context object.

    Examples
    --------

    class Game(ClassArrangement):
        def __init__(self):
            self.timer = TimeManager()

        def stop(self):
            self.context.update(stopped=time.time())
            self.timer.on_stop()

    class TimeManager(Game):
        def __init__(self):
            self.info = TimerInformation()

        def on_stop(self):
            print('Stopped after:', self.context.stopped - self.context.started)

    class TimerInformation(Timer, inherit_context=False):
        def stopped_when(self):
            self.context.stopped_when_called = True
            return self.super_context.stopped

    All of the classes above, Game, Timer and TimerInformation,
    have the attribute (`context` and `super_context`).

    When a Arrangement is subclassed, the subclass enters a new context.
    All its subclasses then may inherit it and then modify it.

    When a Arrangement subclass' subclass has set `inherit_context` to False,
    then a new context is bound to it. The last subclass accesses the top-level context using
    `super_context` and the further subclasses access one context further so on.

    Note that it might be especially useful if those classes are singletons,
    however you may use :class:`InstanceArrangement` for instance-context families.
    """

    def __init_subclass__(
            cls,
            parent=None,
            inherit_context=None,
            reset_init=False,
            extends_implementation=False
    ):
        """
        When a new subclass is created, handle its access to the local context.
        Set :param:`extends_implementation` to True if you want to override this subclass
        for behavioral changes, not for a typical usage.
        """
        if parent is None:
            parent = super()
        inherit_args = (cls.inherit_context, inherit_context)

        if inherit_args.count(None) == 0:
            raise ValueError('cannot set inherit_context= both on a class and during subclassing')

        inherit_context = not any(inherit_args)
        super_context = parent._get_context()
        if inherit_context and super_context is not None:
            context = super_context
        else:
            context = cls._create_context(super_context)
        cls._context = context
        if reset_init:
            cls.__init__ = _init_arrangement

    @functools.cached_property
    def context(self) -> Context:
        """Get the current context. Note: this is the proper API for modifying it."""
        context = self._get_context()
        if self.read_only_context & ReadOnlyLevel.local_context:
            context = _ReadOnlyContextWrapper(context)
        return context

    @functools.cached_property
    def super_context(self) -> Context | None:
        """Get the current super-context. Note: this is the proper API for modifying it."""
        super_context = self._get_super_context(self.context)
        if super_context is not None and self.read_only_context & ReadOnlyLevel.super_context:
            super_context = _ReadOnlyContextWrapper(super_context)
        return super_context


class Arrangement(ClassArrangement, extends_implementation=True):
    # We want docs! >:(
    __init__ = _init_arrangement

    def __new__(cls, *args, **kwargs):
        if args:
            parent, *args = args
        else:
            # We don't even check kwargs, as 'bind' is an untitled positional argument
            parent = None
        context = cls._context
        context.instance = True
        super_context = None
        self = object.__new__(cls)
        cls._instance_super_registry[id(self)] = parent
        context[id(self)] = cls._create_context(super_context)
        return self

    def _get_context(self):
        """Get the current context."""
        contexts = super(ClassArrangement, self)._get_context()
        return contexts[id(self)]

    def _get_super_context(self, context: Context):
        """Get the current super-context."""
        super_contexts = super_context = super(ClassArrangement, type(self))._get_super_context(context)
        if super_contexts is not None:
            assert getattr(super_contexts, 'instance', False)
            super_context = super_contexts[id(self._instance_super_registry[id(self)])]
        return super_context

# TODO:
# I.  Hooks. An idea no. 1: on_context_update(key)(old_value, new_value).
# II. Cached properties for instance context families supplied automagically (classes
#     provided) within a proper decorator (name ideas: leaves(), children(), (family_)?members()).
