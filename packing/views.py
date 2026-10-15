import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Product
from .services import recommend_box, recommend_for_order


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


def _is_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _serialize(result):
    totals = {
        "total_volume": str(result.total_volume),
        "total_weight": str(result.total_weight),
    }
    if result.box is None:
        return {"error": "No box can fit this order.", **totals}, 422
    box = {"id": result.box.id, "name": result.box.name, "cost": str(result.box.cost)}
    return {"box": box, **totals}, 200


@csrf_exempt
@require_POST
def recommend_box_view(request):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _error("Invalid JSON body.", 400)

    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        return _error("'items' must be a non-empty list.", 400)

    quantities = {}
    for entry in raw_items:
        if (
            not isinstance(entry, dict)
            or not _is_positive_int(entry.get("product_id"))
            or not _is_positive_int(entry.get("quantity"))
        ):
            return _error(
                "Each item needs an integer 'product_id' and 'quantity' >= 1.", 400
            )
        pid = entry["product_id"]
        quantities[pid] = quantities.get(pid, 0) + entry["quantity"]

    products = Product.objects.in_bulk(quantities.keys())
    missing = sorted(set(quantities) - set(products))
    if missing:
        return _error(f"Unknown product ids: {missing}", 404)

    items = [(products[pid], qty) for pid, qty in quantities.items()]
    body, status = _serialize(recommend_box(items))
    return JsonResponse(body, status=status)


@require_GET
def order_recommendation_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not order.items.exists():
        return _error("Order has no items.", 400)
    body, status = _serialize(recommend_for_order(order))
    return JsonResponse({"order_id": order.id, **body}, status=status)
