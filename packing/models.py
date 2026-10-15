from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models

POSITIVE = [MinValueValidator(Decimal("0.01"))]


def _dec(digits=8, places=2):
    return models.DecimalField(
        max_digits=digits, decimal_places=places, validators=POSITIVE
    )


class Box(models.Model):
    name = models.CharField(max_length=20, unique=True)
    length = _dec()
    width = _dec()
    height = _dec()
    cost = _dec()
    max_weight = _dec(places=3)
    max_volume = models.DecimalField(max_digits=26, decimal_places=6, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["max_weight", "max_volume"], name="box_weight_volume_idx"),
            models.Index(fields=["cost"], name="box_cost_idx"),
        ]

    def save(self, *args, **kwargs):
        self.max_volume = self.length * self.width * self.height
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @classmethod
    def candidates(cls, total_volume, total_weight):
        return cls.objects.filter(
            max_volume__gte=total_volume, max_weight__gte=total_weight
        ).order_by("cost", "max_volume", "id")


class Product(models.Model):
    name = models.CharField(max_length=20)
    length = _dec()
    width = _dec()
    height = _dec()
    weight = _dec(places=3)

    @property
    def volume(self):
        return self.length * self.width * self.height

    def __str__(self):
        return self.name


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    def totals(self):
        items = list(self.items.select_related("product"))
        volume = sum((i.product.volume * i.quantity for i in items), Decimal("0"))
        weight = sum((i.product.weight * i.quantity for i in items), Decimal("0"))
        return volume, weight


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"], name="orderitem_order_product_uniq"
            ),
        ]
