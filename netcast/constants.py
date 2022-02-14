from netcast.tools.symbol import Symbol

from jaraco.collections import Greatest, Least

__all__ = (
    "MISSING",
    "GREATEST",
    "LEAST"
)

MISSING = Symbol("missing")
GREATEST = Greatest()
LEAST = Least()
