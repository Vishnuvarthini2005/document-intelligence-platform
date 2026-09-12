"""Financial calculation validation.

Implements the minimum checks required per document type (case-study
Table 7). Validation is computed ONLY from fields actually present in the
extracted data - if a field required for a specific check is missing, that
check is reported as NOT_APPLICABLE rather than assuming a value.

Because the extractor returns a flexible (not fixed-schema) set of field
names, this module looks values up by trying a list of common aliases for
each concept (case-insensitive, punctuation-insensitive) before giving up.
"""
import re
from typing import Optional

from app.core.config import get_settings
from app.schemas.extraction import ValidationCheck, ValidationResult

settings = get_settings()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _find_value(data: dict, aliases: list[str]) -> Optional[float]:
    """Looks up a numeric value from extracted_data by trying alias key names."""
    normalized = {_norm(k): v for k, v in data.items()}
    for alias in aliases:
        key = _norm(alias)
        if key in normalized:
            entry = normalized[key]
            val = entry.get("value") if isinstance(entry, dict) else entry
            num = _to_number(val)
            if num is not None:
                return num
    return None


def _to_number(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        negative = s.startswith("(") and s.endswith(")")
        s = re.sub(r"[^0-9.\-]", "", s)
        if s in ("", "-", "."):
            return None
        try:
            num = float(s)
            return -abs(num) if negative else num
        except ValueError:
            return None
    return None


def _tolerance(reported: float) -> float:
    return max(settings.validation_tolerance_abs, abs(reported) * settings.validation_tolerance_pct)


def _check(name: str, formula: str, operands: dict, calculated: Optional[float], reported: Optional[float]) -> ValidationCheck:
    if calculated is None or reported is None:
        return ValidationCheck(
            name=name, formula=formula, operands=operands,
            calculated_value=calculated, reported_value=reported,
            variance=None, status="NOT_APPLICABLE",
            message="Required field(s) not present in the extracted document.",
        )
    variance = round(calculated - reported, 2)
    status = "PASS" if abs(variance) <= _tolerance(reported) else "FAIL"
    return ValidationCheck(
        name=name, formula=formula, operands=operands,
        calculated_value=round(calculated, 2), reported_value=round(reported, 2),
        variance=variance, status=status,
    )


def _overall(checks: list[ValidationCheck]) -> str:
    if not checks:
        return "NOT_APPLICABLE"
    if any(c.status == "FAIL" for c in checks):
        return "FAIL"
    if all(c.status == "NOT_APPLICABLE" for c in checks):
        return "NOT_APPLICABLE"
    return "PASS"


def validate_invoice(data: dict) -> ValidationResult:
    subtotal = _find_value(data, ["subtotal"])
    tax = _find_value(data, ["tax_amount", "tax"])
    discount = _find_value(data, ["discount"]) or 0.0
    total = _find_value(data, ["total_amount", "total"])

    checks = []
    if subtotal is not None or tax is not None or total is not None:
        calculated = None
        if subtotal is not None and tax is not None:
            calculated = subtotal + tax - discount
        checks.append(_check(
            "invoice_total_check", "subtotal + tax_amount - discount",
            {"subtotal": subtotal, "tax_amount": tax, "discount": discount},
            calculated, total,
        ))

    cash_paid = _find_value(data, ["cash_paid", "cash", "amount_paid"])
    change = _find_value(data, ["change", "change_due"])
    if cash_paid is not None and total is not None:
        checks.append(_check(
            "cash_change_check", "cash_paid - total_amount", {"cash_paid": cash_paid, "total_amount": total},
            cash_paid - total, change,
        ))

    return ValidationResult(checks=checks, overall_status=_overall(checks))


def validate_balance_sheet(data: dict) -> ValidationResult:
    assets = _find_value(data, ["total_assets"])
    liabilities = _find_value(data, ["total_liabilities"])
    equity = _find_value(data, ["total_equity", "shareholders_equity", "total_capital_and_liabilities"])

    checks = []
    calculated = None
    if liabilities is not None and equity is not None:
        calculated = liabilities + equity
    elif equity is not None and assets is not None and liabilities is None:
        calculated = None  # can't derive liabilities safely without assumption
    checks.append(_check(
        "balance_sheet_equation", "total_liabilities + total_equity",
        {"total_liabilities": liabilities, "total_equity": equity}, calculated, assets,
    ))
    return ValidationResult(checks=checks, overall_status=_overall(checks))


def validate_profit_and_loss(data: dict) -> ValidationResult:
    revenue = _find_value(data, ["revenue", "total_income", "interest_earned"])
    other_income = _find_value(data, ["other_income"]) or 0.0
    cogs = _find_value(data, ["cost_of_sales", "cogs"])
    gross_profit = _find_value(data, ["gross_profit"])
    opex = _find_value(data, ["operating_expenses"])
    operating_profit = _find_value(data, ["operating_profit"])
    tax = _find_value(data, ["tax"]) or 0.0
    net_profit = _find_value(data, ["net_profit"])

    checks = []
    calc_gp = None
    if revenue is not None and cogs is not None:
        calc_gp = revenue - cogs
    checks.append(_check(
        "gross_profit_check", "revenue - cost_of_sales",
        {"revenue": revenue, "cost_of_sales": cogs}, calc_gp, gross_profit,
    ))

    calc_op = None
    if gross_profit is not None and opex is not None:
        calc_op = gross_profit - opex
    checks.append(_check(
        "operating_profit_check", "gross_profit - operating_expenses",
        {"gross_profit": gross_profit, "operating_expenses": opex}, calc_op, operating_profit,
    ))

    calc_net = None
    if operating_profit is not None:
        calc_net = operating_profit - tax
    checks.append(_check(
        "net_profit_check", "operating_profit - tax",
        {"operating_profit": operating_profit, "tax": tax}, calc_net, net_profit,
    ))

    return ValidationResult(checks=checks, overall_status=_overall(checks))


def validate_cash_flow(data: dict) -> ValidationResult:
    ocf = _find_value(data, ["operating_cash_flow", "net_cash_flow_from_operating_activities"])
    icf = _find_value(data, ["investing_cash_flow", "net_cash_flow_from_investing_activities"])
    fcf = _find_value(data, ["financing_cash_flow", "net_cash_flow_from_financing_activities"])
    net_change = _find_value(data, ["net_change_in_cash", "net_increase_in_cash"])
    opening = _find_value(data, ["opening_cash"])
    closing = _find_value(data, ["closing_cash"])

    checks = []
    calc_change = None
    if ocf is not None and icf is not None and fcf is not None:
        calc_change = ocf + icf + fcf
    checks.append(_check(
        "net_change_in_cash_check", "operating_cash_flow + investing_cash_flow + financing_cash_flow",
        {"operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf},
        calc_change, net_change,
    ))

    calc_closing = None
    if opening is not None and net_change is not None:
        calc_closing = opening + net_change
    checks.append(_check(
        "closing_cash_check", "opening_cash + net_change_in_cash",
        {"opening_cash": opening, "net_change_in_cash": net_change}, calc_closing, closing,
    ))

    return ValidationResult(checks=checks, overall_status=_overall(checks))


VALIDATORS = {
    "invoice": validate_invoice,
    "balance_sheet": validate_balance_sheet,
    "profit_and_loss": validate_profit_and_loss,
    "cash_flow_statement": validate_cash_flow,
}


def run_validation(document_type: str, extracted_data: dict) -> ValidationResult:
    validator = VALIDATORS.get(document_type)
    if not validator:
        return ValidationResult(checks=[], overall_status="NOT_APPLICABLE", issues=["Unknown document type"])
    return validator(extracted_data)
