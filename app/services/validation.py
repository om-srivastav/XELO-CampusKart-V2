import re
from decimal import Decimal, InvalidOperation

from flask import abort, request


def field(name, minimum=0, maximum=200, default=""):
    value = request.form.get(name, default).strip()
    if not minimum <= len(value) <= maximum:
        abort(400, f"{name.replace('_', ' ').title()} must contain {minimum}–{maximum} characters.")
    return value


def integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def money(value):
    try:
        amount = Decimal(value)
        if (
            not amount.is_finite()
            or amount < 0
            or amount > Decimal("99999999.99")
            or amount != amount.quantize(Decimal(".01"))
        ):
            raise ValueError()
        return amount
    except (InvalidOperation, ValueError, TypeError):
        abort(400, "Enter a non-negative price with at most two decimal places.")


def phone(value):
    if not value:
        return ""
    if not re.fullmatch(r"[+\d\s()\-]+", value):
        abort(400, "Enter a valid phone number with country code.")
    number = re.sub(r"[^\d]", "", value)
    if len(number) == 10 and number[0] in "6789":
        number = "91" + number
    if not re.fullmatch(r"[1-9]\d{7,14}", number):
        abort(400, "Enter a valid phone number with country code.")
    return number


def password():
    value = request.form.get("password", "")
    if len(value) < 12 or len(value) > 128 or value != request.form.get("confirm"):
        abort(400, "Passwords must match and contain 12–128 characters.")
    return value


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"
