"""
Shared utility functions used across SupplyFlow apps.
"""

import hashlib
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.utils import timezone


def generate_ref_number(prefix: str, organization, model_class, field_name: str) -> str:
    """
    Generate a sequential reference number scoped to an organization and date.

    Pattern: {PREFIX}-{YYYYMMDD}-{XXXX}
    Examples: PO-20260308-0001, SHP-20260308-0012
    """
    today = date.today().strftime("%Y%m%d")
    prefix_str = f"{prefix}-{today}"

    last = (
        model_class.objects.filter(
            organization=organization,
            **{f"{field_name}__startswith": prefix_str},
        )
        .order_by(f"-{field_name}")
        .values_list(field_name, flat=True)
        .first()
    )

    if last:
        seq = int(last.split("-")[-1]) + 1
    else:
        seq = 1

    return f"{prefix_str}-{seq:04d}"


def money_round(value: Decimal, places: int = 2) -> Decimal:
    """
    Round a monetary value to the specified decimal places using
    banker's rounding (ROUND_HALF_UP).
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quantize_str = Decimal(10) ** -places
    return value.quantize(quantize_str, rounding=ROUND_HALF_UP)


def business_days_between(start_date: date, end_date: date) -> int:
    """
    Count the number of business days (Mon-Fri) between two dates, inclusive.
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    total = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0 .. Friday=4
            total += 1
        current += timedelta(days=1)
    return total


def add_business_days(start_date: date, days: int) -> date:
    """Return the date that is `days` business days after `start_date`."""
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def percentage_change(old_value: Decimal, new_value: Decimal) -> Optional[Decimal]:
    """
    Calculate percentage change between two values.
    Returns None if old_value is zero to avoid division by zero.
    """
    if old_value == 0:
        return None
    change = ((new_value - old_value) / abs(old_value)) * 100
    return money_round(change)


def generate_short_uuid() -> str:
    """Generate a URL-friendly short identifier from a UUID4 (first 12 hex chars)."""
    return uuid.uuid4().hex[:12]


def file_checksum(file_obj) -> str:
    """
    Compute SHA-256 checksum of an uploaded file object.
    Useful for verifying document integrity (contracts, inspection reports).
    """
    sha = hashlib.sha256()
    for chunk in file_obj.chunks(4096):
        sha.update(chunk)
    return sha.hexdigest()


def date_ranges_overlap(start1: date, end1: date, start2: date, end2: date) -> bool:
    """Check whether two date ranges overlap."""
    return start1 <= end2 and start2 <= end1


def days_until(target_date: date) -> int:
    """Number of calendar days from today until target_date (negative if past)."""
    return (target_date - timezone.now().date()).days
