"""Clean, safe module demonstrating good patterns for false-positive validation."""

from typing import Optional


def compute_tax(amount: float, rate: float = 0.05) -> float:
    """Calculate tax for a given transaction amount.

    Args:
        amount: Base transaction amount.
        rate: Tax rate as a decimal.

    Returns:
        Computed tax amount.
    """
    if amount <= 0:
        return 0.0
    return amount * rate


class TaxCalculator:
    """Encapsulates tax calculation operations."""

    def __init__(self, default_rate: float = 0.05) -> None:
        """Initialize calculator with standard rate."""
        self.default_rate = default_rate

    def calculate(self, base_val: float, override_rate: Optional[float] = None) -> float:
        """Calculate final tax."""
        applied_rate = override_rate if override_rate is not None else self.default_rate
        return compute_tax(base_val, applied_rate)
