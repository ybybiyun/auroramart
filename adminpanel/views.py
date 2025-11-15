from asyncio.log import logger
from django.utils import timezone
from django.shortcuts import render, redirect
from onlineshopfront.models import Product, Category, SubCategory, Customer, Order, OrderItem
from django.db.models import Q, F, Sum, FloatField, Exists, OuterRef
from .forms import ProductForm, CategoryForm, StaffUserCreationForm, StockUpdateForm, SubCategoryForm, StaffUserRoleForm, BulkProductUploadForm
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import HiddenProduct
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
import csv, io
from decimal import Decimal
from django.db import transaction
from django.contrib.auth import logout
from django.http import HttpResponse
from urllib.parse import urlencode


def logout_simple(request):
    logout(request)
    return redirect('adminpanel:login')

def groups_required(*names):
    def check(u):
        if not u.is_authenticated:
            return False
        if u.is_superuser or u.groups.filter(name='Admin').exists():
            return True
        return u.groups.filter(name__in=names).exists()
    return user_passes_test(check)

@user_passes_test(lambda u: u.is_superuser)
def staff_list(request):
    q = request.GET.get('q', '').strip()
    users = User.objects.filter(is_staff=True).order_by('username')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )
    # Ensure required role groups exist (idempotent)
    for name in ['Admin','Manager','Merchandiser','Inventory','Support']:
        Group.objects.get_or_create(name=name)
    paginator = Paginator(users, 25)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'adminpanel/staff_list.html', {
        'users': page_obj,
        'q': q,
    })

@user_passes_test(lambda u: u.is_superuser)
def staff_create(request):
    if request.method == 'POST':
        form = StaffUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Staff '{user.username}' created.")
            return redirect('adminpanel:staff_list')
    else:
        form = StaffUserCreationForm()
    return render(request, 'adminpanel/staff_create.html', {'form': form})

@user_passes_test(lambda u: u.is_superuser)
def staff_edit(request, pk):
    user = get_object_or_404(User, pk=pk, is_staff=True)
    if request.method == 'POST':
        form = StaffUserRoleForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated roles for '{user.username}'.")
            return redirect('adminpanel:staff_list')
    else:
        form = StaffUserRoleForm(instance=user)
    return render(request, 'adminpanel/staff_edit.html', {'form': form, 'staff_user': user})

@login_required
def adminpanel(request):
    category_id = request.GET.get('category')  
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
    q = request.GET.get('q','').strip()
    category_ids = request.GET.getlist('categories')
    subcategory_ids = request.GET.getlist('subcategories')
    visibility_filter = request.GET.getlist('visibility')  # values: 'visible','hidden'
    sort = request.GET.get('sort','').strip()

    qs = Product.objects.all()

    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))

    if category_ids:
        qs = qs.filter(product_subcategory__category__category_id__in=category_ids)

    if subcategory_ids:
        qs = qs.filter(product_subcategory__subcategory_id__in=subcategory_ids)

    # visibility logic
    vis = set(visibility_filter)
    if vis and vis != {'visible','hidden'}:
        if vis == {'hidden'}:
            qs = qs.filter(hidden_flag=True)
        elif vis == {'visible'}:
            qs = qs.filter(hidden_flag=False)

    if sort == 'sku_asc':
        qs = qs.order_by('sku')
    elif sort == 'sku_desc':
        qs = qs.order_by('-sku')
    elif sort == 'name_asc':
        qs = qs.order_by('product_name')
    elif sort == 'name_desc':
        qs = qs.order_by('-product_name')
    else:
        qs = qs.order_by('sku')

    categories = Category.objects.order_by('category_name').prefetch_related('category_subcategory')
    subcategories = SubCategory.objects.order_by('subcategory_name')

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request,'adminpanel/catalogue_list.html',{
        'products': page_obj,
        'q': q,
        'category_ids': category_ids,
        'subcategory_ids': subcategory_ids,
        'visibility_filter': visibility_filter,
        'categories': categories,
        'subcategories': subcategories,
        'sort': sort,
    })

@login_required
@groups_required('Manager','Merchandiser')
def bulk_products_upload(request):
    from .forms import BulkProductUploadForm
    if request.method == 'POST':
        form = BulkProductUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['file']
            update_existing = form.cleaned_data['update_existing']
            try:
                data = f.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                messages.error(request, "File must be UTF-8 encoded.")
                return redirect('adminpanel:bulk_products_upload')

            reader = csv.DictReader(io.StringIO(data))
            if not reader.fieldnames:
                messages.error(request, "Missing header row.")
                return redirect('adminpanel:bulk_products_upload')

            header_lower = {h.lower(): h for h in reader.fieldnames}
            required_cols = {'sku','name','category','qty','price'}
            missing = required_cols - set(header_lower.keys())
            if missing:
                messages.error(request, f"Missing required columns: {', '.join(sorted(missing))}")
                return redirect('adminpanel:bulk_products_upload')

            created = updated = 0
            errors = []

            # detect fields present on Product
            product_field_names = {f.name for f in Product._meta.fields}
            has_hidden_flag = 'hidden_flag' in product_field_names

            with transaction.atomic():
                for line_no, row in enumerate(reader, start=2):
                    row_l = {k.lower(): (v or '').strip() for k, v in row.items()}

                    sku         = row_l.get('sku')
                    name        = row_l.get('name')
                    cat_name    = row_l.get('category')              
                    sub_name    = row_l.get('subcategory','')        
                    desc        = row_l.get('description','')        
                    qty_raw     = row_l.get('qty')
                    price_raw   = row_l.get('price')
                    reorder_raw = row_l.get('reorder_qty') or row_l.get('reorder_quantity') or ''
                    rating_raw  = row_l.get('rating','')
                    hidden_raw  = row_l.get('hidden','').lower()

                    if not sku or not name:
                        errors.append(f"Line {line_no}: missing sku or name")
                        continue
                    if not cat_name:
                        errors.append(f"Line {line_no}: category required")
                        continue

                    try:
                        qty = int(qty_raw)
                    except:
                        errors.append(f"Line {line_no}: bad qty '{qty_raw}'")
                        continue

                    try:
                        price = Decimal(price_raw)
                    except:
                        errors.append(f"Line {line_no}: bad price '{price_raw}'")
                        continue

                    try:
                        reorder_qty = int(reorder_raw) if reorder_raw else 0
                    except:
                        errors.append(f"Line {line_no}: bad reorder_qty '{reorder_raw}' (using 0)")
                        reorder_qty = 0

                    try:
                        rating = float(rating_raw) if rating_raw else 0.0
                    except:
                        errors.append(f"Line {line_no}: bad rating '{rating_raw}' (using 0.0)")
                        rating = 0.0

                    category = Category.objects.filter(category_name__iexact=cat_name).first()
                    if not category:
                        category = Category.objects.create(category_name=cat_name)

                    subcat = None
                    if sub_name:
                        subcat = SubCategory.objects.filter(
                            category=category,
                            subcategory_name__iexact=sub_name
                        ).first()
                        if not subcat:
                            subcat = SubCategory.objects.create(category=category, subcategory_name=sub_name)

                    hidden_flag = hidden_raw in {'1','true','yes','y'}

                    prod = Product.objects.filter(sku=sku).first()
                    if prod:
                        if update_existing:
                            prod.product_name = name
                            prod.product_category = cat_name
                            if subcat:
                                prod.product_subcategory = subcat
                            if desc:
                                prod.product_description = desc
                            prod.quantity_on_hand = qty
                            if 'reorder_quantity' in product_field_names:
                                prod.reorder_quantity = reorder_qty
                            if 'unit_price' in product_field_names:
                                prod.unit_price = float(price)
                            if 'product_rating' in product_field_names:
                                prod.product_rating = rating
                            if has_hidden_flag:
                                prod.hidden_flag = hidden_flag
                            prod.save()
                            updated += 1
                        else:
                            errors.append(f"Line {line_no}: SKU '{sku}' exists (skipped)")
                    else:
                        create_kwargs = dict(
                            sku=sku,
                            product_name=name,
                            product_description=desc or '—',
                            product_category=cat_name,
                            quantity_on_hand=qty,
                        )
                        if 'reorder_quantity' in product_field_names:
                            create_kwargs['reorder_quantity'] = reorder_qty
                        if 'unit_price' in product_field_names:
                            create_kwargs['unit_price'] = float(price)
                        if 'product_rating' in product_field_names:
                            create_kwargs['product_rating'] = rating
                        if subcat:
                            create_kwargs['product_subcategory'] = subcat
                        if has_hidden_flag:
                            create_kwargs['hidden_flag'] = hidden_flag
                        try:
                            Product.objects.create(**create_kwargs)
                            created += 1
                        except Exception as e:
                            errors.append(f"Line {line_no}: create failed ({e})")

            if created:
                messages.success(request, f"Created {created} products.")
            if updated:
                messages.success(request, f"Updated {updated} products.")
            if errors:
                preview = " | ".join(errors[:8]) + (" ..." if len(errors) > 8 else "")
                messages.error(request, f"{len(errors)} issues: {preview}")
            return redirect('adminpanel:catalogue_list')
    else:
        form = BulkProductUploadForm()
    return render(request, 'adminpanel/bulk_products_upload.html', {'form': form})

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
    else:
        form = CategoryForm()
    return render(request, 'adminpanel/category_form.html', {'form': form})

@login_required
@groups_required('Manager', 'Merchandiser')
def subcategory_create(request):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subcategory created.")
            return redirect('adminpanel:catalogue_list')
    else:
        form = SubCategoryForm()
    return render(request, 'adminpanel/subcategory_form.html', {'form': form})

@login_required
@groups_required('Manager', 'Merchandiser')
def catalogue_export(request):
    q = request.GET.get('q','').strip()
    category_ids = request.GET.getlist('categories')
    subcategory_ids = request.GET.getlist('subcategories')
    visibility_filter = request.GET.getlist('visibility')
    sort = request.GET.get('sort','').strip()

    qs = (Product.objects
          .all()
          .select_related('product_subcategory', 'product_subcategory__category'))

    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))
    if category_ids:
        qs = qs.filter(product_subcategory__category__category_id__in=category_ids)
    if subcategory_ids:
        qs = qs.filter(product_subcategory__subcategory_id__in=subcategory_ids)

    product_field_names = {f.name for f in Product._meta.fields}
    has_hidden_flag = 'hidden_flag' in product_field_names
    if not has_hidden_flag:
        qs = qs.annotate(hidden_exists=Exists(HiddenProduct.objects.filter(product__pk=OuterRef('pk'))))

    vis = set(visibility_filter)
    if vis and vis != {'visible','hidden'}:
        if 'hidden' in vis:
            qs = qs.filter(hidden_flag=True) if has_hidden_flag else qs.filter(hidden_exists=True)
        elif 'visible' in vis:
            qs = qs.filter(hidden_flag=False) if has_hidden_flag else qs.filter(hidden_exists=False)

    if sort == 'sku_asc':
        qs = qs.order_by('sku')
    elif sort == 'sku_desc':
        qs = qs.order_by('-sku')
    elif sort == 'name_asc':
        qs = qs.order_by('product_name')
    elif sort == 'name_desc':
        qs = qs.order_by('-product_name')
    else:
        qs = qs.order_by('sku')

    headers = ['SKU','Name','Category','Subcategory','Qty','Reorder Qty','Unit Price','Rating','Hidden']
    rows = []
    for p in qs:
        cat = p.product_subcategory.category.category_name if p.product_subcategory and p.product_subcategory.category_id else ''
        sub = p.product_subcategory.subcategory_name if p.product_subcategory else ''
        hidden = (getattr(p, 'hidden_flag', None) if has_hidden_flag else getattr(p, 'hidden_exists', False)) or False
        rows.append([
            p.sku,
            p.product_name,
            cat,
            sub,
            getattr(p, 'quantity_on_hand', ''),
            getattr(p, 'reorder_quantity', ''),
            getattr(p, 'unit_price', ''),
            getattr(p, 'product_rating', ''),
            'Yes' if hidden else 'No',
        ])

    stamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="products_{stamp}.csv"'
    writer = csv.writer(resp)
    writer.writerow(headers)
    writer.writerows(rows)
    return resp

@login_required
@groups_required('Manager', 'Inventory')
def inventory_list(request):
    q = (request.GET.get('q') or '').strip()
    show_low = request.GET.get('low') == '1'
    sort = (request.GET.get('sort') or '').strip()

    qs = Product.objects.all()

    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))

    if show_low:
        qs = qs.filter(quantity_on_hand__lte=F('reorder_quantity'))

    if sort == 'sku_asc':
        qs = qs.order_by('sku')
    elif sort == 'sku_desc':
        qs = qs.order_by('-sku')
    elif sort == 'name_asc':
        qs = qs.order_by('product_name')
    elif sort == 'name_desc':
        qs = qs.order_by('-product_name')
    else:
        qs = qs.order_by('sku')

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'adminpanel/inventory_list.html', {
        'products': page_obj,
        'q': q,
        'show_low': show_low,
        'sort': sort,
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
def inventory_export(request):
    q = (request.GET.get('q') or '').strip()
    show_low = request.GET.get('low') == '1'

    qs = Product.objects.all().only('sku','product_name','quantity_on_hand','reorder_quantity') \
         .order_by('sku')

    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(product_name__icontains=q))
    if show_low:
        qs = qs.filter(quantity_on_hand__lte=F('reorder_quantity'))

    headers = ['SKU', 'Name', 'Qty On Hand', 'Reorder Qty', 'Status']
    rows = []
    for p in qs:
        status = 'LOW' if p.quantity_on_hand <= p.reorder_quantity else 'OK'
        rows.append([p.sku, p.product_name, p.quantity_on_hand, p.reorder_quantity, status])

    stamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="inventory_{stamp}.csv"'
    writer = csv.writer(resp)
    writer.writerow(headers)
    writer.writerows(rows)
    return resp


@login_required
@groups_required('Manager', 'Support')
def customer_list(request):
    q = (request.GET.get('q') or '').strip()
    page = request.GET.get('page')

    sel_age = request.GET.getlist('age')
    sel_gender = request.GET.getlist('gender')
    sel_employment = request.GET.getlist('employment')
    sel_occupation = request.GET.getlist('occupation')
    sel_education = request.GET.getlist('education')
    sel_household = request.GET.getlist('household_size')
    sel_children = request.GET.getlist('children')  # '1' or '0'
    sel_income = request.GET.getlist('income')
    sel_prefcat = request.GET.getlist('preferred_category')

    age_ranges = [
        ('15-20', 15, 20),
        ('20-30', 20, 30),
        ('30-40', 30, 40),
        ('40-50', 40, 50),
        ('50-60', 50, 60),
        ('60+', 60, None),
    ]
    income_ranges = [
        ('0-2000', 0, 2000),
        ('2000-5000', 2000, 5000),
        ('5000-10000', 5000, 10000),
        ('10000-20000', 10000, 20000),
        ('20000+', 20000, None),
    ]

    def distinct_values(field):
        return list(
            Customer.objects
            .exclude(**{f"{field}__isnull": True})
            .exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )

    gender_opts = distinct_values('gender')
    employment_opts = distinct_values('employment_status')
    occupation_opts = distinct_values('occupation')
    education_opts = distinct_values('education')
    household_opts = list(
        Customer.objects
        .exclude(household_size__isnull=True)
        .values_list('household_size', flat=True)
        .distinct()
        .order_by('household_size')
    )
    prefcat_opts = distinct_values('preferred_category')

    total = Customer.objects.count()
    qs = Customer.objects.all().order_by('id')
    if total >= 101:
        qs = qs.filter(id__gte=101)

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q) |
            Q(occupation__icontains=q) |
            Q(education__icontains=q) |
            Q(preferred_category__icontains=q)
        )

    if sel_gender:
        qs = qs.filter(gender__in=sel_gender)
    if sel_employment:
        qs = qs.filter(employment_status__in=sel_employment)
    if sel_occupation:
        qs = qs.filter(occupation__in=sel_occupation)
    if sel_education:
        qs = qs.filter(education__in=sel_education)
    if sel_household:
        ints = []
        for v in sel_household:
            try:
                ints.append(int(v))
            except ValueError:
                pass
        if ints:
            qs = qs.filter(household_size__in=ints)
    if sel_children:
        vals = []
        for v in sel_children:
            if v in ('0', '1'):
                vals.append(int(v))
        if vals:
            qs = qs.filter(has_children__in=vals)
    if sel_prefcat:
        qs = qs.filter(preferred_category__in=sel_prefcat)

    if sel_age:
        age_q = Q()
        for label, lo, hi in age_ranges:
            if label in sel_age:
                if hi is None:
                    age_q |= Q(age__gte=lo)
                else:
                    # inclusive lower, exclusive upper to avoid overlap
                    age_q |= Q(age__gte=lo, age__lt=hi)
        if age_q:
            qs = qs.filter(age_q)

    if sel_income:
        inc_q = Q()
        for label, lo, hi in income_ranges:
            if label in sel_income:
                if hi is None:
                    inc_q |= Q(monthly_income__gte=lo)
                else:
                    inc_q |= Q(monthly_income__gte=lo, monthly_income__lt=hi)
        if inc_q:
            qs = qs.filter(inc_q)

    paginator = Paginator(qs, 50)
    customers_page = paginator.get_page(page)

    params = request.GET.copy()
    params.pop('page', None)
    qs_params = params.urlencode()

    return render(request, 'adminpanel/customer_list.html', {
        'customers': customers_page,
        'q': q,
        # options
        'age_ranges': age_ranges,
        'income_ranges': income_ranges,
        'gender_opts': gender_opts,
        'employment_opts': employment_opts,
        'occupation_opts': occupation_opts,
        'education_opts': education_opts,
        'household_opts': household_opts,
        'prefcat_opts': prefcat_opts,
        'sel_age': sel_age,
        'sel_gender': sel_gender,
        'sel_employment': sel_employment,
        'sel_occupation': sel_occupation,
        'sel_education': sel_education,
        'sel_household': sel_household,
        'sel_children': sel_children,
        'sel_income': sel_income,
        'sel_prefcat': sel_prefcat,
        'qs_params': qs_params,
    })

@login_required
@groups_required('Manager', 'Support')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    orders_qs = (Order.objects
                 .filter(customer=customer)
                 .order_by('-order_date')
                 .prefetch_related('order_items__product'))

    page = request.GET.get('page')
    paginator = Paginator(orders_qs, 25)
    orders = paginator.get_page(page)

    total_orders = orders_qs.count()
    total_spent = orders_qs.aggregate(total=Sum('order_price'))['total'] or 0.0

    return render(request, 'adminpanel/customer_detail.html', {
        'customer': customer,
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
    })

