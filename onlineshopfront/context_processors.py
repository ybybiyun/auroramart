from .models import Category
from .models import Cart, CartItem


def site_categories(request):
    """Provide categories for the header/navigation on every template."""
    try:
        cats = Category.objects.all()
    except Exception:
        cats = []
    # compute a simple cart_count: if user has a linked Customer and Cart, sum quantities
    cart_count = 0
    try:
        if request.user and request.user.is_authenticated:
            # try to get customer's cart
            try:
                cust = request.user.customer_profile
                cart = Cart.objects.filter(cart_customer=cust).first()
                if cart:
                    cart_count = sum(ci.quantity for ci in cart.items.all())
            except Exception:
                cart_count = 0
        else:
            # for anonymous users, use session cart stored as {sku: qty}
            sess = getattr(request, 'session', None)
            if sess:
                s = sess.get('cart', {})
                cart_count = sum(int(v) for v in s.values()) if isinstance(s, dict) else 0
    except Exception:
        cart_count = 0

    return {"site_categories": cats, "cart_count": cart_count}
