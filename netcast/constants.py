import enum

from netcast.tools.symbol import Symbol

MISSING = Symbol("missing")


class Break(enum.Enum):
    SKIP = Symbol("skip")
    JUMP = Symbol("jump")
