from __future__ import annotations

import abc
import asyncio
import collections.abc
import functools
import io
import queue
from typing import Type, ForwardRef, Sequence

from netcast.toolkit.collections import AttributeDict, MemoryDict, MemoryList

CT, C = Type["Context"], ForwardRef("Context")


class _Hook:
    prepared_contexts = MemoryList()

    @classmethod
    def before_modify(cls, context, func, *args, **kwargs):
        """Anytime a context is going to be modified, this method is called."""

    @classmethod
    def after_modify(cls, context, func, *args, **kwargs):
        """Anytime a context was modified, this method is called."""

    @classmethod
    def is_prepared(cls, context):
        return context in cls.prepared_contexts

    @classmethod
    def on_prepare(cls, context):
        cls.prepared_contexts.append(context)


class Context(metaclass=abc.ABCMeta):
    """
    All context classes must derive from this class.
    Should not be used directly - choose a proper subclass instead (or create your own).
    If subclassing, remember to call :class:`ModifyHandle` in all modification methods
    in order to make modification hooks work.
    """


def _hooked_method(method, pre_hook=None, post_hook=None, cls=None):
    if method is None:
        raise TypeError(
            f'method {method!r} '
            f'{"of " + repr(cls) + " " if cls is not None else ""}'
            f'does not exist'
        )

    @functools.wraps(method)
    def _method_wrapper(self, *args, **kwargs):
        bound_method = getattr(self, method.__name__)
        callable(pre_hook) and pre_hook(self, bound_method, *args, **kwargs)
        res = method(self, *args, **kwargs)
        callable(post_hook) and post_hook(self, bound_method, *args, **kwargs)
        return res

    return _method_wrapper


def wrap_to_context(bases, hooked_methods=(), name=None, doc=None, init_subclass=None):
    if isinstance(bases, Sequence):
        if not bases:
            raise ValueError('at least 1 base class is required')
        cls = bases[0]
        if len(bases) == 1:
            bases += (Context,)
    else:
        cls = bases
        bases = (cls, Context)
    env = {**({'__doc__': doc} if doc else {})}
    for method in hooked_methods:
        method = (
            getattr(cls, method, None)
            if isinstance(method, str)
            else method
        )
        env[method.__name__] = _hooked_method(
            method, pre_hook=_Hook.before_modify,
            post_hook=_Hook.after_modify, cls=cls
        )
    if name is None:
        cls_name = cls.__name__
        suffix = 'Context'
        if cls_name:
            f = cls_name[0].upper()
            if len(cls_name) > 1:
                name = f + cls_name[1:] + suffix
            else:
                name = f + suffix
        else:
            raise ValueError('class name was not provided')
    if init_subclass is None:
        init_subclass = {}
    return type(name, bases, env, **init_subclass)


_list_modifiers = (
    'append', 'extend', 'insert', 'pop', 'remove', 'reverse', '__setitem__', '__delitem__'
)
_deque_modifiers = _list_modifiers + ('appendleft', 'extendleft', 'popleft')
_dict_modifiers = ('__setitem__',)
_queue_modifiers = ('_put', '_get')
_io_modifiers = ('write', 'read', 'seek', 'close')

ListContext = wrap_to_context(list, _list_modifiers)
DequeContext = wrap_to_context(collections.deque, _deque_modifiers)
DictContext = wrap_to_context(AttributeDict, _dict_modifiers)
ByteArrayContext = wrap_to_context(bytearray, _list_modifiers)
MemoryDictContext = wrap_to_context(MemoryDict, _dict_modifiers)
QueueContext = wrap_to_context(queue.Queue, _queue_modifiers)
PriorityQueueContext = wrap_to_context(queue.PriorityQueue, _queue_modifiers)
LifoQueueContext = wrap_to_context(queue.LifoQueue, _queue_modifiers)
AsyncioQueueContext = wrap_to_context(asyncio.Queue, _queue_modifiers, name='AsyncioQueue')
AsyncioPriorityQueueContext = wrap_to_context(asyncio.PriorityQueue, _queue_modifiers, name='AsyncioPriorityQueueContext')  # noqa: E501
AsyncioLifoQueueContext = wrap_to_context(asyncio.LifoQueue, _queue_modifiers, name='AsyncioLifoQueueContext')  # noqa: E501
FileIOContext = wrap_to_context(io.FileIO, _io_modifiers)
BytesIOContext = wrap_to_context(io.BytesIO, _io_modifiers)
StringIOContext = wrap_to_context(io.StringIO, _io_modifiers)

# shortcuts
LContext = ListContext
DQContext = DequeContext
DContext = DictContext
BContext = BAContext = ByteContext = ByteArrayContext
MDContext = MemoryDictContext
QContext = QueueContext
PQContext = PriorityQueueContext
LQContext = LifoQueueContext
AQContext = AsyncioQueueContext
APQContext = AsyncioPriorityQueueContext
ALQContext = AsyncioLifoQueueContext
FIOContext = FileIOContext
BIOContext = BytesIOContext
SIOContext = StringIOContext
