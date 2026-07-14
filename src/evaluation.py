from __future__ import annotations

from dataclasses import dataclass


class EvaluationBudgetExceeded(RuntimeError):
    """Raised when an optimizer tries to evaluate beyond its NFE budget."""


@dataclass
class EvaluationBudget:
    max_evaluations: int | None = None
    used: int = 0

    @property
    def remaining(self) -> int | None:
        if self.max_evaluations is None:
            return None
        return max(0, self.max_evaluations - self.used)

    def can_consume(self, amount: int = 1) -> bool:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if self.max_evaluations is None:
            return True
        return self.used + amount <= self.max_evaluations

    def consume(self, amount: int = 1) -> None:
        if not self.can_consume(amount):
            raise EvaluationBudgetExceeded(
                f"evaluation budget exceeded: requested {amount}, "
                f"used {self.used}, max {self.max_evaluations}"
            )
        self.used += amount
