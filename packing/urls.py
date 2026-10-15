from django.urls import path

from . import views

urlpatterns = [
    path("api/recommend-box/", views.recommend_box_view, name="recommend-box"),
    path(
        "api/orders/<int:order_id>/recommend-box/",
        views.order_recommendation_view,
        name="order-recommend-box",
    ),
]
