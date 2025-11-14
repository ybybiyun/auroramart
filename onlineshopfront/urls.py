from django.urls import path
from . import views
from . import views_cart

app_name = "onlineshopfront"

urlpatterns = [
    path("", views.index, name="index"),
    path("create-account/", views.create_account, name="create_account"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('myOrders/', views.myOrder, name='myOrder'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('myProfile/', views.myProfile, name='myProfile'),
    path('settings/', views.settings, name='settings'),
    path('profile/complete/', views.complete_profile, name='complete_profile'),
    path("products/", views.product_list, name="product_list"),
    path("products/category/<slug:category_slug>/", views.product_list, name="product_list_by_category"),
    path("products/<str:pk>/", views.product_detail, name="product_detail"),
    path('cart/', views_cart.view_cart, name='view_cart'),
    path('cart/add/<str:sku>/', views_cart.add_to_cart, name='add_to_cart'),
    path('cart/remove/<str:sku>/', views_cart.remove_from_cart, name='remove_from_cart'),
    path('cart/update/', views_cart.update_cart, name='update_cart'),
    path('checkout/', views_cart.checkout, name='checkout'),
    path('checkout/success/<int:order_id>/', views_cart.checkout_success, name='checkout_success'),
]
