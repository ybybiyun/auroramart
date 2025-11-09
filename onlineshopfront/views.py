from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Product, Category, Cart, CartItem
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
User = get_user_model()


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
        # Lookup Category by slug (we added a slug field)
        category = get_object_or_404(Category, slug=category_slug)
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

        login(request, user)
        messages.success(request, 'Account created and logged in')
        return redirect('onlineshopfront:index')

    return render(request, 'onlineshopfront/create_account.html')


def login_view(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password')
        # authenticate by username (we used email as username)
        user = authenticate(request, username=email, password=password)
        if user is None:
            # fallback: maybe username has suffix if duplicate; try by email field
            try:
                u = User.objects.get(email=email)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user:
            login(request, user)

            # Ensure a Customer profile exists and is linked to this user.
            from .models import Customer
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

            # determine whether the customer's profile is incomplete and should be completed
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

            needs_profile = False
            if cust is None:
                needs_profile = True
            else:
                # consider profile incomplete if key fields are missing or default
                if not cust.first_name or not cust.email or not cust.preferred_category or (cust.age == 0):
                    needs_profile = True

            if needs_profile:
                # redirect user to profile completion form
                return redirect('onlineshopfront:complete_profile')

            messages.success(request, 'Signed in')
            return redirect('onlineshopfront:index')
        else:
            messages.error(request, 'Invalid credentials')
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
        return redirect('onlineshopfront:index')

    # GET: render form prefilled
    context = {'customer': cust}
    return render(request, 'onlineshopfront/complete_profile.html', context)