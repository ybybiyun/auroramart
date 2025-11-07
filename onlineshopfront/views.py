from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Product, Category


def index(request):
    # show top-rated products and top-level categories
    featured = Product.objects.all().order_by('-product_rating')[:12]
    categories = Category.objects.all()
    return render(request, "onlineshopfront/index.html", {"featured": featured, "categories": categories})


def product_list(request, category_slug=None):
    category = None
    # use actual model field names
    products = Product.objects.all().order_by("product_name")
    q = request.GET.get("q")
    if q:
        products = products.filter(product_name__icontains=q) | products.filter(sku__icontains=q)

    if category_slug:
        # Category model stores `category_name` (not slug). Try matching by name (replace dashes with spaces).
        lookup_name = category_slug.replace('-', ' ')
        category = get_object_or_404(Category, category_name__iexact=lookup_name)
        # Products store category as text in `product_category`
        products = products.filter(product_category__iexact=category.category_name)

    # pagination
    paginator = Paginator(products, 24)  # 24 products per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()
    return render(request, "onlineshopfront/product_list.html", {"category": category, "products": page_obj, "q": q, "categories": categories})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    return render(request, "onlineshopfront/product_detail.html", {"product": product, "categories": categories})
from django.shortcuts import render

def myOrder(request):
    return render(request, "onlineshopfront/myOrders.html")

def myProfile(request):
    return render(request, "onlineshopfront/myProfile.html")

def settings(request):
    return render(request, "onlineshopfront/settings.html")