"""Financial EMI calculator — estimates only."""

from __future__ import annotations

from typing import Any, Optional


def calculate_emi(
    principal: float,
    annual_rate_percent: Optional[float],
    tenure_months: int,
    moratorium_months: int = 0,
    repayment_frequency: str = "monthly",
    moratorium_interest_known: bool = False,
) -> dict[str, Any]:
    if principal <= 0:
        raise ValueError("Loan amount must be positive")
    if tenure_months <= 0:
        raise ValueError("Tenure must be positive")
    if moratorium_months < 0:
        raise ValueError("Moratorium cannot be negative")
    if moratorium_months >= tenure_months:
        raise ValueError("Moratorium must be less than tenure")

    warnings: list[str] = []
    if annual_rate_percent is None:
        return {
            "estimated": True,
            "principal": principal,
            "annual_interest_rate": None,
            "tenure_months": tenure_months,
            "moratorium_months": moratorium_months,
            "repayment_frequency": repayment_frequency,
            "emi": None,
            "total_interest": None,
            "total_repayment": None,
            "schedule": [],
            "warnings": [
                "Interest rate is not available from an official source. EMI cannot be estimated."
            ],
            "disclaimer": (
                "Estimated figures only. Final terms are determined by the authorized channel partner."
            ),
        }

    if moratorium_months > 0 and not moratorium_interest_known:
        warnings.append(
            "Official source does not specify how interest is treated during moratorium. "
            "EMI schedule assumes repayment begins after moratorium with no assumed interest capitalization."
        )

    periods_per_year = {"monthly": 12, "quarterly": 4, "yearly": 1}.get(repayment_frequency, 12)
    n_repayment = max(1, int(round((tenure_months - moratorium_months) * periods_per_year / 12)))
    r = (annual_rate_percent / 100.0) / periods_per_year

    if r == 0:
        emi = principal / n_repayment
    else:
        emi = principal * r * (1 + r) ** n_repayment / ((1 + r) ** n_repayment - 1)

    schedule = []
    balance = principal
    total_interest = 0.0

    for i in range(1, n_repayment + 1):
        interest = balance * r
        principal_component = emi - interest
        if principal_component > balance:
            principal_component = balance
            emi_period = principal_component + interest
        else:
            emi_period = emi
        balance = max(0.0, balance - principal_component)
        total_interest += interest
        schedule.append(
            {
                "period": i,
                "emi": round(emi_period, 2),
                "principal": round(principal_component, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2),
            }
        )

    return {
        "estimated": True,
        "principal": round(principal, 2),
        "annual_interest_rate": annual_rate_percent,
        "tenure_months": tenure_months,
        "moratorium_months": moratorium_months,
        "repayment_frequency": repayment_frequency,
        "emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_repayment": round(principal + total_interest, 2),
        "schedule": schedule,
        "warnings": warnings,
        "disclaimer": (
            "Estimated figures only. Actual sanction terms may differ and are determined by "
            "the authorized channel partner and applicable government rules."
        ),
    }
