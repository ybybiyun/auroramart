from django.contrib import admin
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.adminpanel, name='adminpanel'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='adminpanel:login'), name='logout'),
    path('accounts/create/', views.account_create, name='account_create'),

    path('catalogue/', views.catalogue_list, name='catalogue_list'),
    path('catalogue/new/', views.product_create, name='product_create'),
    path('catalogue/<str:pk>/edit/', views.product_edit, name='product_edit'),
    path('catalogue/<str:pk>/delete/', views.product_delete, name='product_delete'),
    path('catalogue/<str:pk>/toggle/', views.product_toggle_active, name='product_toggle'),
    path('catalogue/<str:pk>/toggle_hidden/', views.product_toggle_hidden, name='product_toggle_hidden'),

    path('category/new/', views.category_create, name='category_create'),
    path('category/<int:pk>/edit/', views.category_edit, name='category_edit'),

    path('subcategory/new/', views.subcategory_create, name='subcategory_create'),
    path('subcategory/<int:pk>/edit/', views.subcategory_edit, name='subcategory_edit'),
    path('category/merge/<int:source_pk>/<int:target_pk>/', views.category_merge, name='category_merge'),

    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/<str:pk>/stock/', views.inventory_update_stock, name='inventory_update_stock'),

    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
]