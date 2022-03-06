from __future__ import annotations  # Python 3.8

import enum
import functools
import operator
from typing import Any, Callable, Union

from jaraco.collections import BijectiveMap

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
    rop_func: _DelegateT
    irop_func: _DelegateT

    def __init__(
        self,
        component: ComponentT,
        evaluation_order: int = PRE | POSTINV,
        inplace: bool = False
    ):
        super().__init__(component, evaluation_order)
        self.inplace = inplace

    def eval_reduce_func(self, *operands) -> Any:
        """Compute op(...(op(numbers[0], numbers[1])), numbers[len(numbers) - 1])"""
        op_func = self.op_func
        if self.inplace:
            op_func = self.iop_func
        return functools.reduce(op_func, operands)

    def eval_func(self, *operands) -> Any:
        return self.eval_reduce_func(*operands)


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


# Reversible operations
OP_REVERSE_MAP = dict(BijectiveMap({
    operator.add: operator.sub,
    operator.iadd: operator.isub,
    operator.mul: operator.truediv,
    operator.imul: operator.itruediv,
    operator.pow: _revert_pow,
    operator.ipow: _irevert_pow,
    divmod: _revert_divmod,
}))

# Reversible with loss
OP_REVERSE_MAP[operator.floordiv] = operator.mul

# Irreversible operations
OP_REVERSE_MAP[operator.and_] = _null_delegate
OP_REVERSE_MAP[operator.iand] = _null_delegate

OP_REVERSE_MAP[operator.or_] = _null_delegate
OP_REVERSE_MAP[operator.ior] = _null_delegate

OP_REVERSE_MAP[operator.mod] = _null_delegate
OP_REVERSE_MAP[operator.imod] = _null_delegate


class Add(DelegateExpression):
    """Addition expression."""
    op_func = operator.add
    iop_func = operator.iadd

    def eval_func(self, *operands) -> Any:
        if not self.inplace:
            return sum(*operands)
        return self.eval_reduce_func(*operands)


class Concat(DelegateExpression):
    """Concatenation expression."""
    op_func = operator.concat
    iop_func = operator.iconcat


class Subtract(DelegateExpression):
    """Subtraction expression."""
    op_func = operator.sub
    iop_func = operator.isub


class Multiply(DelegateExpression):
    """Multiplication expression."""
    op_func = operator.mul
    iop_func = operator.imul


class Divide(DelegateExpression):
    """Division expression."""
    op_func = operator.truediv
    iop_func = operator.itruediv


class FloorDivide(DelegateExpression):
    """Floor division expression."""
    op_func = operator.floordiv
    iop_func = operator.ifloordiv


class LShift(DelegateExpression):
    """Shift left (a << b) expression."""
    op_func = operator.lshift
    iop_func = operator.ilshift


class RShift(DelegateExpression):
    """Shift right (a >> b) expression."""
    op_func = operator.rshift
    iop_func = operator.irshift


class MatMultiply(DelegateExpression):
    """Matrix multiplication (a @ b) expression."""
    op_func = operator.rshift
    iop_func = operator.irshift


