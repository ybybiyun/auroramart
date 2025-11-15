from django.contrib import admin
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.adminpanel, name='adminpanel'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_simple, name='logout'),
    
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),

    path('catalogue/', views.catalogue_list, name='catalogue_list'),
    path('catalogue/new/', views.product_create, name='product_create'),
    path('catalogue/<str:pk>/edit/', views.product_edit, name='product_edit'),
    path('catalogue/<str:pk>/delete/', views.product_delete, name='product_delete'),
    path('catalogue/<str:pk>/toggle/', views.product_toggle_active, name='product_toggle'),
    path('catalogue/<str:pk>/toggle_hidden/', views.product_toggle_hidden, name='product_toggle_hidden'),
    path('catalogue/bulk-upload/', views.bulk_products_upload, name='bulk_products_upload'),
    path('catalogue/export/', views.catalogue_export, name='catalogue_export'),
    path('catalogue/category/new/', views.category_create, name='category_create'),
    path('catalogue/subcategory/new/', views.subcategory_create, name='subcategory_create'),

    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/<str:pk>/stock/', views.inventory_update_stock, name='inventory_update_stock'),
    path('inventory/export/', views.inventory_export, name='inventory_export'),

    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
]