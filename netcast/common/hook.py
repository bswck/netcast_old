from __future__ import annotations
from typing import Any, ClassVar

from traitlets import Bunch

from netcast.common.context import Arrangement


class Hook(Arrangement):
    """Before send/after receive data handler."""
    source: ClassVar[Any]
    """
    A source template from the proper conversion module.
    See also :package:`netcast.conversions`, from where it can be imported.
    """

    def bunch(self) -> Bunch:
        """Produce a metadata bunch of the source."""


class AfterReceive(Hook):
    def after_receive(self, data, **params):
        """
        Interpret a raw data. It might be a JSON string, XML string or bytes.
        It should use the :attr:`source` set during the construction.
        """
        raise NotImplementedError


class BeforeSend(Hook):
    def before_send(self, data, **params):
        """
        Prepare the data to send.
        """
        raise NotImplementedError
