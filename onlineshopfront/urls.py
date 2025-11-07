from django.urls import path
from . import views

app_name = "onlineshopfront"

urlpatterns = [
    path("", views.index, name="index"),
    path('myOrders/', views.myOrder, name='myOrder'),
    path('myProfile/', views.myProfile, name='myProfile'),
    path('settings/', views.settings, name='settings'),
    path("products/", views.product_list, name="product_list"),
    path("products/category/<slug:category_slug>/", views.product_list, name="product_list_by_category"),
    # Product primary key is a string `sku`, so accept string PKs here
    path("products/<str:pk>/", views.product_detail, name="product_detail"),
]
