from __future__ import annotations  # Python 3.8

import enum
import functools
import operator
from typing import Any, Callable, Union

try:
    import numpy
except ImportError:
    NUMPY = False
else:
    NUMPY = True

from netcast import ComponentT



class EvaluationOrder(enum.IntFlag):
    PRE_SERIALIZATION = 1 << 0
    PRE_SERIALIZATION_INVERTED = 1 << 1
    POST_DESERIALIZATION = 1 << 2
    POST_DESERIALIZATION_INVERTED = 1 << 3

    def validate(self, flags: int | EvaluationOrder):
        mutex_msg = "mutually exclusive listed execution order flags: %s"
        mutex_flags = []

        if (flags & self.PRE_SERIALIZATION) and (flags & self.PRE_SERIALIZATION_INVERTED):
            mutex_flags.append("PRE_SERIALIZATION and PRE_SERIALIZATION_INVERTED")

        if (flags & self.POST_DESERIALIZATION) and (flags & self.POST_DESERIALIZATION_INVERTED):
            mutex_flags.append("POST_DESERIALIZATION and POST_DESERIALIZATION_INVERTED")

        if mutex_flags:
            raise ValueError(mutex_msg % ", ".join(mutex_flags))

        ambiguity_msg = (
            "%s and %s execution order flags "
            "doubles the expression evaluation in a common direction which is ambiguous "
            "and unsupported; expression redesign or checking for mistakes is recommended"
        )

        if (flags & self.PRE_SERIALIZATION) and (flags & self.POST_DESERIALIZATION):
            mutex_flags.append("PRE_SERIALIZATION and POST_SERIALIZATION")
        if (
            (flags & self.POST_DESERIALIZATION_INVERTED)
            and (flags & self.POST_DESERIALIZATION_INVERTED)
        ):
            mutex_flags.append("PRE_SERIALIZATION_INVERTED and POST_SERIALIZATION_INVERTED")

        if mutex_flags:
            raise ValueError(ambiguity_msg % ", ".join(mutex_flags))

PRE = PRE_SERIALIZATION = EvaluationOrder.PRE_SERIALIZATION
PREINV = PRE_SERIALIZATION_INVERTED = EvaluationOrder.PRE_SERIALIZATION_INVERTED
POST = POST_DESERIALIZATION = EvaluationOrder.POST_DESERIALIZATION
POSTINV = POST_DESERIALIZATION_INVERTED = EvaluationOrder.POST_DESERIALIZATION_INVERTED


class Expression:
    """
    Expressions are component mix-ins that declare various pre-serialization
    and post-deserialization operations to automate processing.
    """

    def __init__(
        self,
        component: ComponentT,
        evaluation_order: int = PRE | POSTINV
    ):
        self.component = component
        self.evaluation_order = evaluation_order

    def eval_func(self, *args, **kwargs) -> Any:
        raise NotImplementedError


class DelegateExpression(Expression):
    op_func: _DelegateT
    iop_func: _DelegateT
    oprev_func: _DelegateT
    ioprev_func: _DelegateT

    def __init__(
        self,
        component: ComponentT,
        evaluation_order: int = PRE | POSTINV,
        inplace: bool = False
    ):
        super().__init__(component, evaluation_order)
        self.inplace = inplace

    def cumulative_eval_func(self, *operands) -> Any:
        """Compute op(...(op(numbers[0], numbers[1])), numbers[len(numbers) - 1])"""
        op_func = self.op_func
        if self.inplace:
            op_func = self.iop_func
        return functools.reduce(op_func, operands)

    def eval_func(self, *operands) -> Any:
        return self.cumulative_eval_func(*operands)

    def revert_func(self, *operands):
        if self.inplace:
            oprev_func = getattr(self, "ioprev_func", None)
        else:
            oprev_func = getattr(self, "oprev_func", None)
        if oprev_func is None:
            raise NotImplementedError
        return functools.reduce(oprev_func, operands)

_DelegateT = Union[Callable[[Any, Any], Any], Callable[[DelegateExpression, Any, Any], Any]]


def _null_delegate(a, _):
    return a


def _revert_pow(a, b):
    return a ** (1/b)


def _irevert_pow(a, b):
    a **= (1/b)
    return a


def _revert_divmod(a, b):
    n, r = a
    return n * b + r


class Add(DelegateExpression):
    """Addition expression."""
    op_func = operator.add
    iop_func = operator.iadd
    oprev_func = operator.sub
    ioprev_func = operator.isub

    def eval_func(self, *operands) -> Any:
        if not self.inplace:
            return sum(*operands)
        return self.cumulative_eval_func(*operands)


class Concat(DelegateExpression):
    """Concatenation expression."""
    op_func = operator.concat
    iop_func = operator.iconcat
    oprev_func = _null_delegate
    ioprev_func = _null_delegate


class Subtract(DelegateExpression):
    """Subtraction expression."""
    op_func = operator.sub
    iop_func = operator.isub
    oprev_func = operator.add
    ioprev_func = operator.iadd


class Multiply(DelegateExpression):
    """Multiplication expression."""
    op_func = operator.mul
    iop_func = operator.imul
    oprev_func = operator.truediv
    ioprev_func = operator.itruediv


class Divide(DelegateExpression):
    """Division expression."""
    op_func = operator.truediv
    iop_func = operator.itruediv
    oprev_func = operator.mul
    ioprev_func = operator.imul


class FloorDivide(DelegateExpression):
    """Floor division expression."""
    op_func = operator.floordiv
    iop_func = operator.ifloordiv
    oprev_func = operator.mul
    ioprev_func = operator.imul


class LShift(DelegateExpression):
    """Shift left (a << b) expression."""
    op_func = operator.lshift
    iop_func = operator.ilshift
    oprev_func = operator.rshift
    ioprev_func = operator.irshift


class RShift(DelegateExpression):
    """Shift right (a >> b) expression."""
    op_func = operator.rshift
    iop_func = operator.irshift
    oprev_func = operator.lshift
    ioprev_func = operator.ilshift


class MatMultiply(DelegateExpression):
    """Matrix multiplication (a @ b) expression."""
    op_func = operator.rshift
    iop_func = operator.irshift
    # TODO: matrix division?
    if NUMPY:
        oprev_func = ioprev_func = numpy.divide
