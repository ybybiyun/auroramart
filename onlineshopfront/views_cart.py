from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Product, Cart, CartItem, Customer
from django.contrib import messages


def _get_or_create_session_cart(session):
    cart = session.get('cart')
    if cart is None:
        session['cart'] = {}
        session.modified = True
        cart = session['cart']
    return cart


def add_to_cart(request, sku):
    product = get_object_or_404(Product, pk=sku)
    qty = int(request.POST.get('quantity', 1)) if request.method == 'POST' else 1

    if request.user.is_authenticated:
        # ensure customer exists
        try:
            cust = request.user.customer_profile
        except Exception:
            cust = None
        if cust is None:
            # create a minimal customer to attach cart
            try:
                cust = Customer.objects.create(user=request.user, email=request.user.email or None, age=0, gender='Male', employment_status='Full-time', occupation='', education='Secondary', household_size=1, has_children=0, monthly_income=0.0, preferred_category='')
            except Exception:
                cust = None

        cart, _ = Cart.objects.get_or_create(cart_customer=cust)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': qty})
        if not created:
            item.quantity += qty
            item.save()
        messages.success(request, f'Added {product.product_name} to cart')
        return redirect(request.META.get('HTTP_REFERER') or reverse('onlineshopfront:product_list'))
    else:
        sess_cart = _get_or_create_session_cart(request.session)
        sess_cart[sku] = sess_cart.get(sku, 0) + qty
        request.session.modified = True
        messages.success(request, f'Added {product.product_name} to cart (guest)')
        return redirect(request.META.get('HTTP_REFERER') or reverse('onlineshopfront:product_list'))


def view_cart(request):
    items = []
    total = 0.0
    if request.user.is_authenticated:
        try:
            cust = request.user.customer_profile
            cart = Cart.objects.filter(cart_customer=cust).first()
            if cart:
                for ci in cart.items.select_related('product').all():
                    subtotal = ci.quantity * ci.product.unit_price
                    items.append({'sku': ci.product.sku, 'name': ci.product.product_name, 'price': ci.product.unit_price, 'quantity': ci.quantity, 'subtotal': subtotal})
                    total += subtotal
        except Exception:
            items = []
    else:
        sess = request.session.get('cart', {})
        for sku, qty in sess.items():
            try:
                p = Product.objects.get(pk=sku)
                subtotal = int(qty) * p.unit_price
                items.append({'sku': p.sku, 'name': p.product_name, 'price': p.unit_price, 'quantity': int(qty), 'subtotal': subtotal})
                total += subtotal
            except Product.DoesNotExist:
                continue

    # pop any inline cart notice from session
    notice = None
    try:
        notice = request.session.pop('cart_notice', None)
    except Exception:
        notice = None

    return render(request, 'onlineshopfront/cart.html', {'items': items, 'total': total, 'cart_notice': notice})


def remove_from_cart(request, sku):
    if request.user.is_authenticated:
        try:
            cust = request.user.customer_profile
            cart = Cart.objects.filter(cart_customer=cust).first()
            if cart:
                CartItem.objects.filter(cart=cart, product_id=sku).delete()
        except Exception:
            pass
    else:
        sess = request.session.get('cart', {})
        if sku in sess:
            del sess[sku]
            request.session.modified = True

    # Do not add a flash message here to avoid showing it in the header area.
    return redirect('onlineshopfront:view_cart')


def update_cart(request):
    if request.method != 'POST':
        return redirect('onlineshopfront:view_cart')

    updates = {k.replace('qty_',''): int(v) for k,v in request.POST.items() if k.startswith('qty_')}
    if request.user.is_authenticated:
        try:
            cust = request.user.customer_profile
            cart = Cart.objects.filter(cart_customer=cust).first()
            if cart:
                for sku, qty in updates.items():
                    if qty <= 0:
                        CartItem.objects.filter(cart=cart, product_id=sku).delete()
                    else:
                        ci = CartItem.objects.filter(cart=cart, product_id=sku).first()
                        if ci:
                            ci.quantity = qty
                            ci.save()
        except Exception:
            pass
    else:
        sess = request.session.get('cart', {})
        for sku, qty in updates.items():
            if qty <= 0:
                sess.pop(sku, None)
            else:
                sess[sku] = qty
        request.session.modified = True

    # set an inline cart notice in session instead of a global flash message
    try:
        request.session['cart_notice'] = 'Cart updated'
        request.session.modified = True
    except Exception:
        pass
    return redirect('onlineshopfront:view_cart')
