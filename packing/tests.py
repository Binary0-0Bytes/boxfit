import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Box, Order, OrderItem, Product
from .services import compute_totals, fits_dimensions, recommend_box, recommend_for_order


def make_box(name, l, w, h, cost, max_weight):
    return Box.objects.create(
        name=name, length=Decimal(str(l)), width=Decimal(str(w)),
        height=Decimal(str(h)), cost=Decimal(str(cost)),
        max_weight=Decimal(str(max_weight)),
    )


def make_product(name, l, w, h, weight):
    return Product.objects.create(
        name=name, length=Decimal(str(l)), width=Decimal(str(w)),
        height=Decimal(str(h)), weight=Decimal(str(weight)),
    )


def make_order(*lines):
    order = Order.objects.create()
    for product, qty in lines:
        OrderItem.objects.create(order=order, product=product, quantity=qty)
    return order


class ModelTests(TestCase):
    def test_box_max_volume_computed_on_save(self):
        box = make_box("S", 2, 3, 4, 1, 5)
        box.refresh_from_db()
        self.assertEqual(box.max_volume, Decimal("24"))

    def test_box_max_volume_updates_when_dimensions_change(self):
        box = make_box("S", 2, 3, 4, 1, 5)
        box.length = Decimal("10")
        box.save()
        box.refresh_from_db()
        self.assertEqual(box.max_volume, Decimal("120"))

    def test_product_volume(self):
        self.assertEqual(make_product("A", 2, 3, 4, 1).volume, Decimal("24"))

    def test_duplicate_product_in_order_rejected(self):
        p = make_product("A", 1, 1, 1, 1)
        order = make_order((p, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(order=order, product=p, quantity=2)


class TotalsTests(TestCase):
    def setUp(self):
        self.a = make_product("A", 1, 2, 3, "0.5")
        self.b = make_product("B", 2, 2, 2, "1.25")

    def test_compute_totals(self):
        self.assertEqual(
            compute_totals([(self.a, 2), (self.b, 1)]), (Decimal("20"), Decimal("2.25"))
        )

    def test_order_totals(self):
        order = make_order((self.a, 2), (self.b, 1))
        self.assertEqual(order.totals(), (Decimal("20"), Decimal("2.25")))

    def test_empty_order_totals_are_zero(self):
        self.assertEqual(Order.objects.create().totals(), (Decimal("0"), Decimal("0")))


class CandidatesTests(TestCase):
    def test_filters_by_volume_and_weight_cheapest_first(self):
        make_box("Small", 2, 2, 2, 1, 50)
        make_box("Mid", 4, 4, 4, 3, 50)
        make_box("Pricey", 5, 5, 5, 9, 50)
        make_box("Weak", 5, 5, 5, 2, 1)
        names = [b.name for b in Box.candidates(Decimal("20"), Decimal("5"))]
        self.assertEqual(names, ["Mid", "Pricey"])

    def test_boundaries_are_inclusive(self):
        make_box("Exact", 2, 2, 2, 1, 5)
        self.assertEqual(Box.candidates(Decimal("8"), Decimal("5")).count(), 1)


class FitsDimensionsTests(TestCase):
    def test_fits_when_rotated(self):
        box = make_box("Flat", 3, 2, 1, 1, 10)
        self.assertTrue(fits_dimensions(box, [make_product("Card", 1, 2, 3, 1)]))

    def test_too_long_does_not_fit(self):
        box = make_box("Cube", 3, 3, 3, 1, 10)
        self.assertFalse(fits_dimensions(box, [make_product("Pole", 10, 1, 1, 1)]))

    def test_all_products_must_fit(self):
        box = make_box("Cube", 3, 3, 3, 1, 10)
        ok = make_product("Ok", 1, 1, 1, 1)
        bad = make_product("Bad", 4, 1, 1, 1)
        self.assertFalse(fits_dimensions(box, [ok, bad]))


class RecommendBoxTests(TestCase):
    def test_picks_cheapest_valid_box(self):
        make_box("Large", 10, 10, 10, 9, 50)
        make_box("Medium", 5, 5, 5, 4, 50)
        make_box("Small", 2, 2, 2, 1, 50)
        item = make_product("Mug", 3, 3, 3, 1)
        self.assertEqual(recommend_box([(item, 1)]).box.name, "Medium")

    def test_cost_tie_prefers_smaller_box(self):
        make_box("Bigger", 10, 10, 10, 4, 50)
        make_box("Smaller", 5, 5, 5, 4, 50)
        item = make_product("Mug", 1, 1, 1, 1)
        self.assertEqual(recommend_box([(item, 1)]).box.name, "Smaller")

    def test_exact_volume_fit_accepted(self):
        make_box("Exact", 2, 2, 2, 1, 10)
        item = make_product("Cube", 2, 2, 2, 1)
        self.assertEqual(recommend_box([(item, 1)]).box.name, "Exact")

    def test_weight_over_limit_skips_box(self):
        make_box("Light", 10, 10, 10, 1, 5)
        make_box("Heavy", 10, 10, 10, 3, 50)
        item = make_product("Anvil", 2, 2, 2, 20)
        self.assertEqual(recommend_box([(item, 1)]).box.name, "Heavy")

    def test_exact_weight_limit_accepted(self):
        make_box("B", 10, 10, 10, 1, 5)
        item = make_product("Brick", 2, 2, 2, 5)
        self.assertIsNotNone(recommend_box([(item, 1)]).box)

    def test_quantity_pushes_order_into_bigger_box(self):
        make_box("Small", 2, 2, 2, 1, 50)
        make_box("Big", 4, 4, 4, 5, 50)
        item = make_product("Cube", 2, 2, 2, 1)
        result = recommend_box([(item, 3)])
        self.assertEqual(result.total_volume, Decimal("24"))
        self.assertEqual(result.box.name, "Big")

    def test_enough_volume_but_item_too_long(self):
        make_box("Cube", 3, 3, 3, 1, 50)
        pole = make_product("Pole", 10, 1, 1, 1)
        self.assertIsNone(recommend_box([(pole, 1)]).box)

    def test_cheaper_box_rejected_on_dimensions_falls_back_to_next(self):
        make_box("Short-cheap", 3, 3, 3, 1, 50)
        make_box("Long-pricey", 12, 2, 2, 5, 50)
        pole = make_product("Pole", 10, 1, 1, 1)
        self.assertEqual(recommend_box([(pole, 1)]).box.name, "Long-pricey")

    def test_no_box_fits(self):
        make_box("Small", 2, 2, 2, 1, 5)
        huge = make_product("Huge", 50, 50, 50, 1)
        self.assertIsNone(recommend_box([(huge, 1)]).box)

    def test_no_boxes_exist(self):
        item = make_product("Mug", 1, 1, 1, 1)
        self.assertIsNone(recommend_box([(item, 1)]).box)

    def test_recommend_for_stored_order(self):
        make_box("Medium", 5, 5, 5, 4, 50)
        a = make_product("A", 2, 2, 2, 1)
        b = make_product("B", 1, 1, 1, 1)
        result = recommend_for_order(make_order((a, 2), (b, 3)))
        self.assertEqual(result.box.name, "Medium")
        self.assertEqual(result.total_volume, Decimal("19"))
        self.assertEqual(result.total_weight, Decimal("5"))


class RecommendBoxApiTests(TestCase):
    def setUp(self):
        self.url = reverse("recommend-box")
        make_box("Medium", 5, 5, 5, 4, 50)
        self.product = make_product("Mug", 2, 2, 2, 1)

    def post(self, data, raw=False):
        body = data if raw else json.dumps(data)
        return self.client.post(self.url, body, content_type="application/json")

    def test_success(self):
        resp = self.post({"items": [{"product_id": self.product.id, "quantity": 2}]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["box"]["name"], "Medium")
        self.assertEqual(Decimal(data["total_volume"]), Decimal("16"))
        self.assertEqual(Decimal(data["total_weight"]), Decimal("2"))

    def test_duplicate_product_lines_are_merged(self):
        resp = self.post({"items": [
            {"product_id": self.product.id, "quantity": 1},
            {"product_id": self.product.id, "quantity": 1},
        ]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()["total_weight"]), Decimal("2"))

    def test_no_box_fits_returns_422(self):
        resp = self.post({"items": [{"product_id": self.product.id, "quantity": 1000}]})
        self.assertEqual(resp.status_code, 422)

    def test_empty_items_400(self):
        self.assertEqual(self.post({"items": []}).status_code, 400)

    def test_missing_items_key_400(self):
        self.assertEqual(self.post({}).status_code, 400)

    def test_invalid_json_400(self):
        self.assertEqual(self.post("{not json", raw=True).status_code, 400)

    def test_zero_quantity_400(self):
        resp = self.post({"items": [{"product_id": self.product.id, "quantity": 0}]})
        self.assertEqual(resp.status_code, 400)

    def test_boolean_quantity_400(self):
        resp = self.post({"items": [{"product_id": self.product.id, "quantity": True}]})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_product_404(self):
        resp = self.post({"items": [{"product_id": 9999, "quantity": 1}]})
        self.assertEqual(resp.status_code, 404)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class OrderRecommendationApiTests(TestCase):
    def setUp(self):
        make_box("Medium", 5, 5, 5, 4, 50)
        self.product = make_product("Mug", 2, 2, 2, 1)

    def url(self, order_id):
        return reverse("order-recommend-box", args=[order_id])

    def test_success(self):
        order = make_order((self.product, 2))
        resp = self.client.get(self.url(order.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["box"]["name"], "Medium")

    def test_unknown_order_404(self):
        self.assertEqual(self.client.get(self.url(9999)).status_code, 404)

    def test_empty_order_400(self):
        order = Order.objects.create()
        self.assertEqual(self.client.get(self.url(order.id)).status_code, 400)

    def test_no_box_fits_422(self):
        order = make_order((self.product, 1000))
        self.assertEqual(self.client.get(self.url(order.id)).status_code, 422)
