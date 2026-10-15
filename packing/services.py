from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .models import Box


@dataclass(frozen=True)
class Recommendation:
    box: Optional[Box]
    total_volume: Decimal
    total_weight: Decimal


def compute_totals(items):
    total_volume = sum((p.volume * q for p, q in items), Decimal("0"))
    total_weight = sum((p.weight * q for p, q in items), Decimal("0"))
    return total_volume, total_weight


def fits_dimensions(box, products):
    box_dims = sorted((box.length, box.width, box.height))
    for p in products:
        item_dims = sorted((p.length, p.width, p.height))
        if any(i > b for i, b in zip(item_dims, box_dims)):
            return False
    return True


def recommend_box(items):
    items = list(items)
    total_volume, total_weight = compute_totals(items)
    products = [p for p, _ in items]
    for box in Box.candidates(total_volume, total_weight):
        if fits_dimensions(box, products):
            return Recommendation(box, total_volume, total_weight)
    return Recommendation(None, total_volume, total_weight)


def recommend_for_order(order):
    items = [(i.product, i.quantity) for i in order.items.select_related("product")]
    return recommend_box(items)
