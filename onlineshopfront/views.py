from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from .models import Product, Category, Cart, CartItem
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
User = get_user_model()


def index(request):
    # show top-rated products and top-level categories
    featured = Product.objects.all().order_by('-product_rating')[:12]
    categories = Category.objects.all()
    # Try to predict preferred category for authenticated users and show recommended products
    predicted_category = None
    recommended_products = None
    if request.user.is_authenticated:
        try:
            cust = getattr(request.user, 'customer_profile', None)
            if cust is not None:
                profile = {
                    'age': getattr(cust, 'age', 0) or 0,
                    'household_size': getattr(cust, 'household_size', 0) or 0,
                    'has_children': getattr(cust, 'has_children', 0) or 0,
                    'monthly_income_sgd': getattr(cust, 'monthly_income', None) or getattr(cust, 'monthly_income', 0.0) or 0.0,
                    'gender': getattr(cust, 'gender', 'Male') or 'Male',
                    'employment_status': getattr(cust, 'employment_status', 'Full-time') or 'Full-time',
                    'occupation': getattr(cust, 'occupation', 'Other') or 'Other',
                    'education': getattr(cust, 'education', 'Secondary') or 'Secondary'
                }
                try:
                    from .recommender import predict_preferred_category_from_profile
                    predicted_category = predict_preferred_category_from_profile(profile)
                    if predicted_category:
                        recommended_products = Product.objects.filter(product_category__iexact=predicted_category).order_by('-product_rating')[:8]
                except Exception:
                    # If model not trained or any error occurs, fail gracefully
                    predicted_category = None
                    recommended_products = None
        except Exception:
            pass

    return render(request, "onlineshopfront/index.html", {"featured": featured, "categories": categories, 'predicted_category': predicted_category, 'recommended_products': recommended_products})


def product_list(request, category_slug=None):
    category = None
    products = Product.objects.all().order_by("product_name")
    q = request.GET.get("q")
    if q:
        products = products.filter(product_name__icontains=q) | products.filter(sku__icontains=q)

    if category_slug:
        # Lookup Category by slug (we added a slug field)
        category = get_object_or_404(Category, slug=category_slug)
        # Products store category as text in `product_category`
        products = products.filter(product_category__iexact=category.category_name)

    # pagination
    paginator = Paginator(products, 24)  # 24 products per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Pop any in-card notification set by add_to_cart for non-JS clients
    in_card_notif = None
    try:
        in_card_notif = request.session.pop('in_card_notif', None)
        request.session.modified = True
    except Exception:
        in_card_notif = None

    categories = Category.objects.all()
    return render(request, "onlineshopfront/product_list.html", {"category": category, "products": page_obj, "q": q, "categories": categories, 'in_card_notif': in_card_notif})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()
    # Pop any in-card notification set by add_to_cart for non-JS clients
    in_card_notif = None
    try:
        in_card_notif = request.session.pop('in_card_notif', None)
        request.session.modified = True
    except Exception:
        in_card_notif = None

    return render(request, "onlineshopfront/product_detail.html", {"product": product, "categories": categories, 'in_card_notif': in_card_notif})
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def myOrder(request):
    # Show orders for the logged-in user's customer profile
    try:
        cust = getattr(request.user, 'customer_profile', None)
    except Exception:
        cust = None

    orders_list = []
    if cust is not None:
        from .models import Order
        qs = Order.objects.filter(customer=cust).order_by('-order_date')
        for o in qs:
            orders_list.append({'id': getattr(o, 'order_id', None), 'status': getattr(o, 'order_status', ''), 'total': getattr(o, 'order_price', 0.0)})

    return render(request, "onlineshopfront/myOrders.html", {'orders': orders_list})


@login_required
def order_detail(request, order_id):
    # Show details for a single order belonging to the logged-in user
    try:
        cust = getattr(request.user, 'customer_profile', None)
    except Exception:
        cust = None

    if cust is None:
        # Shouldn't happen because of login_required, but keep safe
        return render(request, "onlineshopfront/order_detail.html", {'error': 'No customer profile found for this user.'})

    from .models import Order
    order = None
    try:
        order = Order.objects.get(pk=order_id, customer=cust)
    except Order.DoesNotExist:
        order = None

    if order is None:
        return render(request, "onlineshopfront/order_detail.html", {'error': 'Order not found.'})

    items = []
    for oi in order.order_items.select_related('product').all():
        items.append({
            'sku': getattr(oi.product, 'sku', ''),
            'name': getattr(oi.product, 'product_name', ''),
            'quantity': getattr(oi, 'quantity', 0),
            'unit_price': getattr(oi, 'unit_price', 0.0),
            'subtotal': getattr(oi, 'quantity', 0) * getattr(oi, 'unit_price', 0.0)
        })

    context = {
        'order': order,
        'items': items,
        'total': getattr(order, 'order_price', 0.0),
    }
    return render(request, "onlineshopfront/order_detail.html", context)

def myProfile(request):
    return render(request, "onlineshopfront/myProfile.html")

def settings(request):
    return render(request, "onlineshopfront/settings.html")


def create_account(request):
    if request.method == 'POST':
        data = request.POST
        email = (data.get('email') or '').strip()
        password = data.get('password')
        confirm = data.get('confirm_password')
        if not email or not password or password != confirm:
            messages.error(request, 'Please provide email and matching passwords')
            return render(request, 'onlineshopfront/create_account.html')

        # ensure username uniqueness (use email as username)
        username = email
        i = 1
        base = username
        while User.objects.filter(username=username).exists():
            username = f"{base}-{i}"
            i += 1

        user = User.objects.create_user(username=username, email=email, password=password)

        # create Customer entry and link
        cust = None
        try:
            age = int(float(data.get('age') or 0))
        except Exception:
            age = 0

        cust = None
        from .models import Customer
        cust = Customer.objects.create(
            user=user,
            first_name=(data.get('first_name') or '').strip() or None,
            last_name=(data.get('last_name') or '').strip() or None,
            phone=(data.get('phone') or '').strip() or None,
            email=email,
            age=age,
            gender=(data.get('gender') or 'Male'),
            employment_status=(data.get('employment_status') or 'Full-time'),
            occupation=(data.get('occupation') or ''),
            education=(data.get('education') or 'Secondary'),
            household_size=int(float(data.get('household_size') or 1)),
            has_children=int(float(data.get('has_children') or 0)),
            monthly_income=float(data.get('monthly_income') or 0.0),
            preferred_category=(data.get('preferred_category') or '')
        )

        # sync first/last name to auth.User
        try:
            fn = (data.get('first_name') or '').strip() or ''
            ln = (data.get('last_name') or '').strip() or ''
            if fn or ln:
                user.first_name = fn
                user.last_name = ln
                user.save()
        except Exception:
            pass

        login(request, user)
        messages.success(request, 'Account created and logged in')
        next_url = request.POST.get('next') or request.GET.get('next') or None
        if next_url:
            return redirect(next_url)
        return redirect('onlineshopfront:index')

    return render(request, 'onlineshopfront/create_account.html')


@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password')
        # For demo/dev: accept any credentials. Find or create a user with this email and log them in
        user = None
        try:
            if email:
                user = User.objects.filter(email__iexact=email).order_by('id').first()
            else:
                user = None
        except Exception:
            user = None

        if user is None:
            # create a new user (use email as base username and ensure uniqueness)
            username = email or 'user'
            i = 1
            base = username
            while User.objects.filter(username=username).exists():
                username = f"{base}-{i}"
                i += 1
            user = User.objects.create_user(username=username, email=email or None)
            # set provided password if any (not required)
            try:
                if password:
                    user.set_password(password)
                    user.save()
            except Exception:
                pass

        # Ensure backend attribute is set so Django login works when we bypass authenticate()
        backend_path = settings.AUTHENTICATION_BACKENDS[0] if getattr(settings, 'AUTHENTICATION_BACKENDS', None) else 'django.contrib.auth.backends.ModelBackend'
        try:
            user.backend = backend_path
        except Exception:
            pass

        # Log the user in (works for existing or newly-created users)
        login(request, user)

        # Ensure a Customer profile exists and is linked to this user.
        from .models import Customer
        cust = None
        try:
            cust = Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            # Try to find by email and attach if possible
            attached = False
            if user.email:
                try:
                    existing = Customer.objects.get(email__iexact=user.email)
                    existing.user = user
                    existing.save()
                    attached = True
                except Customer.DoesNotExist:
                    attached = False

            if not attached:
                # create a minimal Customer record with safe defaults
                try:
                    Customer.objects.create(
                        user=user,
                        first_name=user.first_name or None,
                        last_name=user.last_name or None,
                        phone=None,
                        email=user.email or None,
                        age=0,
                        gender='Male',
                        employment_status='Full-time',
                        occupation='',
                        education='Secondary',
                        household_size=1,
                        has_children=0,
                        monthly_income=0.0,
                        preferred_category='')
                except Exception:
                    # If creation fails for any reason, continue without blocking login
                    pass

            try:
                cust = Customer.objects.get(user=user)
            except Customer.DoesNotExist:
                cust = None

        # merge any session-based guest cart into the user's DB cart
        try:
            sess_cart = request.session.get('cart', {})
            if sess_cart and cust is not None:
                cart_obj, _ = Cart.objects.get_or_create(cart_customer=cust)
                for sku, qty in list(sess_cart.items()):
                    try:
                        prod = Product.objects.get(pk=sku)
                    except Product.DoesNotExist:
                        continue
                    ci, created = CartItem.objects.get_or_create(cart=cart_obj, product=prod, defaults={'quantity': int(qty)})
                    if not created:
                        ci.quantity = ci.quantity + int(qty)
                        ci.save()
                # clear session cart after merging
                try:
                    del request.session['cart']
                    request.session.modified = True
                except Exception:
                    pass
        except Exception:
            # don't let merge errors block login
            pass

        # capture next param early so it can be propagated if profile completion is required
        next_url = request.GET.get('next') or request.POST.get('next') or None

        needs_profile = False
        if cust is None:
            needs_profile = True
        else:
            # consider profile incomplete if key fields are missing or default
            if not cust.first_name or not cust.email or not cust.preferred_category or (cust.age == 0):
                needs_profile = True

        if needs_profile:
            # redirect user to profile completion form and preserve the next param
            if next_url:
                return redirect(f"{reverse('onlineshopfront:complete_profile')}?next={next_url}")
            return redirect('onlineshopfront:complete_profile')

        # After sign-in always go to home page
        messages.success(request, 'Signed in')
        return redirect('onlineshopfront:index')
    return render(request, 'onlineshopfront/login.html')


def logout_view(request):
    logout(request)
    return redirect('onlineshopfront:index')


@login_required
def complete_profile(request):
    from .models import Customer
    try:
        cust = request.user.customer_profile
    except Exception:
        cust = None

    if request.method == 'POST':
        data = request.POST
        if cust is None:
            cust = Customer(user=request.user)

        cust.first_name = (data.get('first_name') or '').strip() or None
        cust.last_name = (data.get('last_name') or '').strip() or None
        cust.phone = (data.get('phone') or '').strip() or None
        cust.email = (data.get('email') or request.user.email) or None
        try:
            cust.age = int(float(data.get('age') or 0))
        except Exception:
            cust.age = 0
        cust.gender = data.get('gender') or 'Male'
        cust.employment_status = data.get('employment_status') or 'Full-time'
        cust.occupation = data.get('occupation') or ''
        cust.education = data.get('education') or 'Secondary'
        try:
            cust.household_size = int(float(data.get('household_size') or 1))
        except Exception:
            cust.household_size = 1
        try:
            cust.has_children = int(float(data.get('has_children') or 0))
        except Exception:
            cust.has_children = 0
        try:
            cust.monthly_income = float(data.get('monthly_income') or 0.0)
        except Exception:
            cust.monthly_income = 0.0
        cust.preferred_category = data.get('preferred_category') or ''
        cust.user = request.user
        cust.save()
        messages.success(request, 'Profile updated')
        # sync to auth.User
        try:
            u = request.user
            u.first_name = cust.first_name or ''
            u.last_name = cust.last_name or ''
            u.save()
        except Exception:
            pass
        # if a next param was provided (from login redirect), go there
        next_url = request.GET.get('next') or request.POST.get('next') or None
        if next_url:
            return redirect(next_url)
        return redirect('onlineshopfront:index')

    # GET: render form prefilled
    context = {'customer': cust}
    return render(request, 'onlineshopfront/complete_profile.html', context)