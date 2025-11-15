from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Product, Cart, CartItem, Customer
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.utils import timezone
from .models import Order, OrderItem
from . import recommender


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
        # compute cart count (sum of quantities)
        try:
            cart_count = cart.items.aggregate(total=models.Sum('quantity'))['total'] or 0
        except Exception:
            cart_count = cart.items.count() if cart else 0

        # For non-JS clients, set an in-card notification in the session so the
        # next rendered page can show a small boxed message near the product's
        # add-to-cart button. For JS clients, the AJAX response will be used.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'product_name': product.product_name, 'cart_count': cart_count})

        try:
            request.session['in_card_notif'] = {'sku': str(product.pk), 'text': f'Added {product.product_name} to cart', 'type': 'success'}
            request.session.modified = True
        except Exception:
            # fallback: use messages
            messages.success(request, f'Added {product.product_name} to cart')

        return redirect(request.META.get('HTTP_REFERER') or reverse('onlineshopfront:product_list'))
    else:
        sess_cart = _get_or_create_session_cart(request.session)
        sess_cart[sku] = sess_cart.get(sku, 0) + qty
        request.session.modified = True

        # compute cart count for guest (sum quantities)
        try:
            cart_count = sum(int(v) for v in request.session.get('cart', {}).values())
        except Exception:
            cart_count = len(request.session.get('cart', {}))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'product_name': product.product_name, 'cart_count': cart_count})

        try:
            request.session['in_card_notif'] = {'sku': str(product.pk), 'text': f'Added {product.product_name} to cart (guest)', 'type': 'success'}
            request.session.modified = True
        except Exception:
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
                    items.append({'sku': ci.product.sku, 'name': ci.product.product_name, 'price': ci.product.unit_price, 'quantity': ci.quantity, 'subtotal': subtotal, 'product': ci.product})
                    total += subtotal
        except Exception:
            items = []
    else:
        sess = request.session.get('cart', {})
        for sku, qty in sess.items():
            try:
                p = Product.objects.get(pk=sku)
                subtotal = int(qty) * p.unit_price
                items.append({'sku': p.sku, 'name': p.product_name, 'price': p.unit_price, 'quantity': int(qty), 'subtotal': subtotal, 'product': p})
                total += subtotal
            except Product.DoesNotExist:
                continue

    notice = request.session.pop('cart_notice', None)

    # --- AI RECOMMENDATION (FIXED) ---
    recommended_products = []
    try:
        cart_skus = [item['sku'] for item in items]
        if cart_skus:
            # FIXED: Correct function name
            recommended_skus = recommender.get_associated_products(cart_skus)
            
            if recommended_skus:
                # Get the Product objects and limit to 4
                recommended_products = Product.objects.filter(sku__in=recommended_skus).exclude(sku__in=cart_skus)[:4]
    except Exception as e:
        print(f"Recommendation failed in cart: {e}")
    # --- END AI RECOMMENDATION ---

    context = {
        'items': items,
        'total': total,
        'cart_notice': notice,
        'recommended_products': recommended_products
    }
    return render(request, 'onlineshopfront/cart.html', context)

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


def checkout(request):
    """Simple checkout page: requires login to place order. GET shows items and total.
    POST will create an Order from the user's cart and clear it, then redirect to success.
    """
    if request.method == 'GET':
        items = []
        total = 0.0
        if request.user.is_authenticated:
            try:
                cust = request.user.customer_profile
                cart = Cart.objects.filter(cart_customer=cust).first()
                if cart:
                    for ci in cart.items.select_related('product').all():
                        subtotal = ci.quantity * ci.product.unit_price
                        items.append({'sku': ci.product.sku, 'name': ci.product.product_name, 'price': ci.product.unit_price, 'quantity': ci.quantity, 'subtotal': subtotal, 'product': ci.product})
                        total += subtotal
            except Exception:
                items = []
        else:
            return redirect(f"{reverse('onlineshopfront:login')}?next={reverse('onlineshopfront:checkout')}")

        initial = {}
        try:
            if request.user.is_authenticated:
                cust = getattr(request.user, 'customer_profile', None)
                if cust is not None:
                    initial['address'] = getattr(cust, 'address', '') or ''
                    initial['postal_code'] = getattr(cust, 'postal_code', '') or ''
                    initial['phone'] = getattr(cust, 'phone', '') or ''
        except Exception:
            pass

        # --- AI RECOMMENDATION (FIXED) ---
        recommended_products = []
        try:
            cart_skus = [item['sku'] for item in items]
            if cart_skus:
                recommended_skus = recommender.get_associated_products(cart_skus)
                if recommended_skus:
                    recommended_products = Product.objects.filter(sku__in=recommended_skus).exclude(sku__in=cart_skus)[:4]
        except Exception as e:
            print(f"Recommendation failed in checkout: {e}")
        # --- END AI RECOMMENDATION ---

        return render(request, 'onlineshopfront/checkout.html', {
            'items': items, 
            'total': total, 
            'initial': initial,
            'recommended_products': recommended_products  # <-- Added this
        })

    # ... your POST logic (no changes needed) ...
    if not request.user.is_authenticated:
        return redirect(f"{reverse('onlineshopfront:login')}?next={reverse('onlineshopfront:checkout')}")

    try:
        cust = request.user.customer_profile
    except Exception:
        cust = None
    if cust is None:
        messages.error(request, 'Please complete your profile before checking out.')
        return redirect('onlineshopfront:complete_profile')

    cart = Cart.objects.filter(cart_customer=cust).first()
    if not cart or not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('onlineshopfront:view_cart')

    # ... (rest of your POST logic) ...
    # ... (no changes needed here) ...
    data = request.POST
    errors = {}
    address = (data.get('address') or '').strip()
    postal_code = (data.get('postal_code') or '').strip()
    phone = (data.get('phone') or '').strip()
    payment_method = (data.get('payment_method') or '').strip()

    if not address:
        errors['address'] = 'Delivery address is required.'
    if not postal_code:
        errors['postal_code'] = 'Postal / ZIP code is required.'
    if not phone:
        errors['phone'] = 'Contact phone is required.'
    if payment_method not in ('Card', 'Paynow', 'Apple Pay'):
        errors['payment_method'] = 'Please select a payment method.'

    if payment_method == 'Card':
        card_number = (data.get('card_number') or '').replace(' ', '')
        card_exp_month = (data.get('card_exp_month') or '').strip()
        card_exp_year = (data.get('card_exp_year') or '').strip()
        card_cvv = (data.get('card_cvv') or '').strip()
        if not (card_number.isdigit() and 12 < len(card_number) <= 19):
            errors['card_number'] = 'Please enter a valid card number.'
        try:
            m = int(card_exp_month)
            y = int(card_exp_year)
            now = timezone.now()
            if not (1 <= m <= 12 and (y > now.year or (y == now.year and m >= now.month))):
                errors['card_expiry'] = 'Card expiry must be in the future.'
        except Exception:
            errors['card_expiry'] = 'Invalid expiry date.'
        if not (card_cvv.isdigit() and len(card_cvv) in (3, 4)):
            errors['card_cvv'] = 'Invalid CVV.'

    if errors:
        items = []
        total = 0.0
        try:
            for ci in cart.items.select_related('product').all():
                subtotal = ci.quantity * ci.product.unit_price
                items.append({'sku': ci.product.sku, 'name': ci.product.product_name, 'price': ci.product.unit_price, 'quantity': ci.quantity, 'subtotal': subtotal})
                total += subtotal
        except Exception:
            items = []
        
        # --- RE-ADD RECOMMENDATIONS ON ERROR ---
        recommended_products = []
        try:
            cart_skus = [item['sku'] for item in items]
            if cart_skus:
                recommended_skus = recommender.get_associated_products(cart_skus)
                if recommended_skus:
                    recommended_products = Product.objects.filter(sku__in=recommended_skus).exclude(sku__in=cart_skus)[:4]
        except Exception:
            pass # Fail silently
        # --- END ---

        form_values = {
            'address': address,
            'postal_code': postal_code,
            'phone': phone,
            'payment_method': payment_method,
        }
        form_values['card_number'] = data.get('card_number', '')
        form_values['card_exp_month'] = data.get('card_exp_month', '')
        form_values['card_exp_year'] = data.get('card_exp_year', '')

        initial = {}
        try:
            cust = getattr(request.user, 'customer_profile', None)
            if cust is not None:
                initial['address'] = getattr(cust, 'address', '') or ''
                initial['postal_code'] = getattr(cust, 'postal_code', '') or ''
                initial['phone'] = getattr(cust, 'phone', '') or ''
        except Exception:
            pass

        return render(request, 'onlineshopfront/checkout.html', {
            'items': items, 
            'total': total, 
            'errors': errors, 
            'form': form_values, 
            'initial': initial,
            'recommended_products': recommended_products # <-- Added this
        })

    # create order
    order = Order.objects.create(order_status='Order Placed', order_date=timezone.now().date(), order_price=0.0, required_date=timezone.now().date(), shipping_fee=0.0, customer=cust)

    selected = request.POST.getlist('selected') if request.method == 'POST' else []
    if selected:
        created_any = False
        for ci in cart.items.select_related('product').all():
            if str(ci.product.sku) in selected:
                OrderItem.objects.create(order=order, product=ci.product, quantity=ci.quantity, unit_price=ci.product.unit_price)
                ci.delete()
                created_any = True
        if not created_any:
            order.delete()
            messages.error(request, 'No selected items were found in your cart.')
            return redirect('onlineshopfront:view_cart')
    else:
        for ci in cart.items.select_related('product').all():
            OrderItem.objects.create(order=order, product=ci.product, quantity=ci.quantity, unit_price=ci.product.unit_price)
        cart.items.all().delete()

    try:
        order.update_order_total()
    except Exception:
        pass

    try:
        if request.session.get('cart'):
            if selected:
                sess = request.session.get('cart', {})
                for s in selected:
                    sess.pop(s, None)
                request.session['cart'] = sess
                request.session.modified = True
            else:
                request.session.pop('cart', None)
                request.session.modified = True
    except Exception:
        pass

    try:
        messages.success(request, 'Order placed successfully.')
    except Exception:
        pass
    return redirect('onlineshopfront:checkout_success', order_id=order.order_id)
    
def checkout_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'onlineshopfront/checkout_success.html', {'order': order})
