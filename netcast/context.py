from __future__ import annotations

import abc
import asyncio
import collections.abc
import contextlib
import queue
import warnings
from typing import Type, ForwardRef

from netcast.toolkit.collections import AttributeDict, MemoryDict, MemoryList

CT, C = Type["Context"], ForwardRef("Context")


class ContextHook:
    MISSING = object()
    prepared_contexts = MemoryList()

    @classmethod
    def on_modify(cls, context, put=MISSING, remove=MISSING):
        """Anytime a context is going to be modified, this method is called."""

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


class ListContext(list, Context):
    """A list context of associated classes or instances."""

    def append(self, item):
        ContextHook.on_modify(self, put=item)
        return super().append(item)

    def extend(self, other):
        ContextHook.on_modify(self, remove=other)
        return super().extend(other)

    def insert(self, i, item):
        ContextHook.on_modify(self, put=item)
        return super().insert(i, item)

    def pop(self, i=-1):
        with contextlib.suppress(IndexError):
            ContextHook.on_modify(self, remove=self[i])
        return super().pop(i)

    def remove(self, item):
        ContextHook.on_modify(self, remove=item)
        return super().remove(item)

    def __setitem__(self, i, item):
        ContextHook.on_modify(self, put=item)
        return super().__setitem__(i, item)

    def __delitem__(self, i):
        with contextlib.suppress(IndexError):
            ContextHook.on_modify(self, remove=self[i])
        return super().__delitem__(i)


class DequeContext(collections.deque, Context):
    def append(self, item):
        ContextHook.on_modify(self, put=item)
        return super().append(item)

    def extend(self, other):
        ContextHook.on_modify(self, remove=other)
        return super().extend(other)

    def insert(self, i, item):
        ContextHook.on_modify(self, put=item)
        return super().insert(i, item)

    def pop(self, i=-1):
        with contextlib.suppress(IndexError):
            ContextHook.on_modify(self, remove=self[i])
        return super().remove(i)

    def remove(self, item):
        ContextHook.on_modify(self, remove=item)
        return super().remove(item)

    def __setitem__(self, i, item):
        ContextHook.on_modify(self, put=item)
        return super().__setitem__(i, item)

    def __delitem__(self, i):
        with contextlib.suppress(IndexError):
            ContextHook.on_modify(self, remove=self[i])
        return super().__delitem__(i)

    def appendleft(self, item):
        ContextHook.on_modify(self, put=item)
        return super().appendleft(item)

    def extendleft(self, other):
        ContextHook.on_modify(self, remove=other)
        return super().extendleft(other)

    def popleft(self):
        with contextlib.suppress(IndexError):
            ContextHook.on_modify(self, remove=self[0])
        return super().popleft()


class DictContext(AttributeDict, Context):
    """A key-value (with key=attribute access) context of associated classes or instances."""

    def __setitem__(self, key, item):
        old = self.get(key, ContextHook.MISSING)
        ContextHook.on_modify(self, put=(key, item, old))
        return super().__setitem__(key, item)


class MemoryDictContext(MemoryDict, Context):
    def __setitem__(self, key, item):
        # XXX transforming the key 3 times?
        old = self.get(self.transform_key(key), ContextHook.MISSING)
        super().__setitem__(key, item)
        ContextHook.on_modify(self, put=(self.transform_key(key), item, old))


def _put(put):
    def __put(self, item):
        ContextHook.on_modify(self, put=item)
        return put(self, item)
    return __put


def _get(get):
    def __get(self):
        item = get(self)
        ContextHook.on_modify(self, remove=item)
        return item
    return __get


def _qc(qc, name=None, doc=None):
    subqc = type(
        name or (qc.__module__.split('.')[0].capitalize() + qc.__name__ + 'Context'),
        (qc, Context),
        {
            '_put': _put(qc._put),
            '_get': _get(qc._get),
            **({} if doc is None else {'__doc__': doc}),
        }
    )
    return subqc


QueueContext = _qc(queue.Queue, 'QueueContext')
PriorityQueueContext = _qc(queue.PriorityQueue, 'PriorityQueueContext')
LifoQueueContext = _qc(queue.LifoQueue, 'LifoQueueContext')

AsyncioQueueContext = _qc(asyncio.Queue)
AsyncioPriorityQueueContext = _qc(asyncio.PriorityQueue)
AsyncioLifoQueueContext = _qc(asyncio.LifoQueue)
