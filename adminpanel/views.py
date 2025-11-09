from django.utils import timezone
from django.shortcuts import render
from onlineshopfront.models import Product, Category, SubCategory, Customer, Order, OrderItem
from django.db.models import Q, F
from .forms import ProductForm, CategoryForm, StaffUserCreationForm, StockUpdateForm, SubCategoryForm
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import HiddenProduct
from django.db.models import Sum, FloatField
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required, user_passes_test

# Create your views here.
def groups_required(*names):
    def check(u):
        return u.is_authenticated and (u.is_superuser or u.groups.filter(name__in=names).exists())
    return user_passes_test(check)

@user_passes_test(lambda u: u.is_superuser)
def account_create(request):
    if request.method == 'POST':
        form = StaffUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Staff account '{user.username}' created.")
            return redirect('adminpanel:adminpanel')
    else:
        form = StaffUserCreationForm()
    return render(request, 'adminpanel/account_create.html', {'form': form})

@login_required
def adminpanel(request):
    category_id = request.GET.get('category')  # Category.category_id
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    today = timezone.now().date()
    default_start = today - timedelta(days=30)
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else default_start
    except ValueError:
        start_date = default_start
    try:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else today
    except ValueError:
        end_date = today

    # Base querysets (optionally filtered by category)
    product_qs = Product.objects.all()
    if category_id:
        product_qs = product_qs.filter(product_subcategory__category_id=category_id)

    # KPIs
    total_skus = product_qs.count()
    low_stock_count = product_qs.filter(quantity_on_hand__lte=F('reorder_quantity')).count()
    totals = product_qs.aggregate(
        total_units=Sum('quantity_on_hand'),
        inventory_value=Sum(F('quantity_on_hand') * F('unit_price'), output_field=FloatField()),
    )
    total_units = totals.get('total_units') or 0
    inventory_value = totals.get('inventory_value') or 0.0

    # Sales from OrderItems within date range (category filtered at item level)
    sales_items = OrderItem.objects.filter(order__order_date__gte=start_date, order__order_date__lte=end_date)
    if category_id:
        sales_items = sales_items.filter(product__product_subcategory__category_id=category_id)
    sales = sales_items.aggregate(
        revenue=Sum(F('quantity') * F('unit_price'), output_field=FloatField()),
        units=Sum('quantity'),
    )
    sales_revenue = sales.get('revenue') or 0.0
    units_sold = sales.get('units') or 0
    orders_count = sales_items.values('order_id').distinct().count()

    # Top sellers (by units)
    top_products = list(
        sales_items.values('product__sku', 'product__product_name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:5]
    )

    categories = Category.objects.all().order_by('category_name')
    return render(request, 'adminpanel/index.html', {
        'categories': categories,
        'category_id': str(category_id) if category_id else '',
        'start_date': start_date.strftime("%Y-%m-%d"),
        'end_date': end_date.strftime("%Y-%m-%d"),
        'total_skus': total_skus,
        'low_stock_count': low_stock_count,
        'total_units': total_units,
        'inventory_value': inventory_value,
        'sales_revenue': sales_revenue,
        'units_sold': units_sold,
        'orders_count': orders_count,
        'top_products': top_products,
    })

@login_required
@groups_required('Manager', 'Merchandiser')
def catalogue_list(request):
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    products = Product.objects.all().select_related('product_subcategory').order_by('-sku')
    if category_id:
        products = products.filter(product_subcategory__category_id=category_id)
    if subcategory_id:
        products = products.filter(product_subcategory_id=subcategory_id)
    if q:
        products = products.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))

    paginator = Paginator(products, 25)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)

    categories = Category.objects.all()
    return render(request, 'adminpanel/catalogue_list.html', {
        'products': products_page,
        'categories': categories,
        'q': q,
        'category_id': category_id,
        'subcategory_id': subcategory_id,
    })

@login_required
@groups_required('Manager', 'Merchandiser')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created")
            return redirect('adminpanel:catalogue_list')
    else:
        form = ProductForm()
    return render(request, 'adminpanel/product_form.html', {'form': form})

@login_required
@groups_required('Manager', 'Merchandiser')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated")
            return redirect('adminpanel:catalogue_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'adminpanel/product_form.html', {'form': form, 'product': product})

@login_required
@groups_required('Manager', 'Merchandiser')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Product deleted")
        return redirect('adminpanel:catalogue_list')
    return render(request, 'adminpanel/product_confirm_delete.html', {'product': product})

@login_required
@groups_required('Manager', 'Merchandiser')
def product_toggle_active(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.active = not product.active
    product.save()
    return redirect('adminpanel:catalogue_list')

@login_required
@groups_required('Manager', 'Merchandiser')
def product_toggle_hidden(request, pk):
    product = get_object_or_404(Product, pk=pk)
    hidden = getattr(product, 'hidden_flag', None)
    if hidden:
        hidden.delete()
        messages.success(request, f"{product.sku} unhidden.")
    else:
        HiddenProduct.objects.create(product=product)
        messages.success(request, f"{product.sku} hidden.")
    return redirect('adminpanel:catalogue_list')

@login_required
@groups_required('Manager', 'Merchandiser')
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
    return redirect('adminpanel:catalogue_list')

@login_required
@groups_required('Manager', 'Merchandiser')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect('adminpanel:catalogue_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'adminpanel/category_form.html', {'form': form, 'category': category})

@login_required
@groups_required('Manager', 'Merchandiser')
def subcategory_create(request):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subcategory created.")
    return redirect('adminpanel:catalogue_list')

@login_required
@groups_required('Manager', 'Merchandiser')
def subcategory_edit(request, pk):
    subcat = get_object_or_404(SubCategory, pk=pk)
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, instance=subcat)
        if form.is_valid():
            form.save()
            messages.success(request, "Subcategory updated.")
            return redirect('adminpanel:catalogue_list')
    else:
        form = SubCategoryForm(instance=subcat)
    return render(request, 'adminpanel/subcategory_form.html', {'form': form, 'subcategory': subcat})

@login_required
@groups_required('Manager')
def category_merge(request, source_pk, target_pk):
    if request.method == 'POST':
        source = get_object_or_404(Category, pk=source_pk)
        target = get_object_or_404(Category, pk=target_pk)
        # Reassign subcategories
        SubCategory.objects.filter(category=source).update(category=target)
        # Reassign products via subcategories already moved
        messages.success(request, f"Merged category {source.category_name} into {target.category_name}.")
        source.delete()
    return redirect('adminpanel:catalogue_list')

@login_required
@groups_required('Manager', 'Inventory')
def inventory_list(request):
    q = request.GET.get('q', '').strip()
    show_low = request.GET.get('low') == '1'
    products = Product.objects.all().order_by('sku')
    if q:
        products = products.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))
    if show_low:
        products = products.filter(quantity_on_hand__lte=F('reorder_quantity'))

    paginator = Paginator(products, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    # Precompute low stock flags
    low_map = {p.sku: (p.quantity_on_hand <= p.reorder_quantity) for p in page_obj}

    return render(request, 'adminpanel/inventory_list.html', {
        'products': page_obj,
        'q': q,
        'show_low': show_low,
        'low_map': low_map,
    })

@login_required
@groups_required('Manager', 'Inventory')
def inventory_update_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = StockUpdateForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Stock updated for {product.sku}")
            return redirect('adminpanel:inventory_list')
    else:
        form = StockUpdateForm(instance=product)
    return render(request, 'adminpanel/inventory_stock_form.html', {
        'form': form,
        'product': product,
    })

@login_required
@groups_required('Manager', 'Support')
def customer_list(request):
    q = request.GET.get('q', '').strip()
    customers = Customer.objects.all().order_by('id')
    if q:
        customers = customers.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    paginator = Paginator(customers, 25)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'adminpanel/customer_list.html', {
        'customers': page_obj,
        'q': q,
    })

@login_required
@groups_required('Manager', 'Support')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = (Order.objects
              .filter(customer=customer)
              .order_by('-order_date')
              .prefetch_related('order_items__product'))
    total_orders = orders.count()
    total_spent = sum(o.order_price for o in orders)
    return render(request, 'adminpanel/customer_detail.html', {
        'customer': customer,
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
    })

