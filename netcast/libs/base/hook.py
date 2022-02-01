from __future__ import annotations
from typing import Any, ClassVar

from netcast.toolkit.arrangements import Arrangement
from netcast.toolkit.contexts import DictContext


class Hook(Arrangement, config=True):
    """Before send/after receive data handler."""
    source: ClassVar[Any]
    """
    A source template from the proper conversion module.
    See also :package:`netcast.cast`, from where it can be imported.
    """

    context_class = DictContext


class ReceiveHook(Hook):
    new_context = True

    def on_receive(self, data, **params):
        """
        Interpret a raw data. It might be a JSON string, XML string or bytes.
        It should use the :attr:`source` set during the construction.
        """
        raise NotImplementedError


class SendHook(Hook):
    new_context = True

    def on_send(self, data, **params):
        """
        Prepare the data to send.
        """
        raise NotImplementedError
