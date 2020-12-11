import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from shop.models import Product, ProductCategory, Category
default_context = {'categories': Category.objects.filter(is_public=True)}

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_API_KEY))


# Create your views here.
def product_view(request, slug):
    product = Product.objects.get(slug=slug)
    quantity = 1
    if request.user and request.user.is_authenticated:
        cart_product = request.user.cart.all_products().filter(product=product).first()
        if cart_product:
            quantity = cart_product.quantity
    context = {'product': product, 'quantity': quantity, 'related_products': product.recommended_products.all()}
    context.update(default_context)
    return render(request, 'ecommerce/product_view.html', context=context)


@csrf_exempt
@login_required(login_url='user.login')
def add_to_cart(request):
    cart = request.user.cart
    product = Product.objects.get(id=int(request.POST.get('product_id')))
    cart.add_product(product, int(request.POST.get('quantity', 1)))
    if request.is_ajax() or request.POST.get('is_ajax'):
        return HttpResponse(cart.all_products().count())
    return redirect('shop:view_product', slug=product.slug)


@login_required(login_url='user.login')
@csrf_exempt
def add_to_wishlist(request):
    wish_list = request.user.wish_list
    product = Product.objects.get(id=int(request.POST.get('product_id')))
    wish_list.add_product(product)
    return HttpResponse(status=200)


@login_required(login_url='user.login')
def cart_view(request):
    cart = request.user.cart
    context = {'cart_products': cart.all_products(), 'cart': cart}
    context.update(default_context)
    return render(request, 'ecommerce/cart.html', context=context)


@login_required(login_url='user.login')
def checkout(request):
    cart = request.user.cart
    context = {'cart_products': cart.all_products(), 'cart': cart}
    context.update(default_context)
    return render(request, 'ecommerce/checkout.html', context=context)


from .models import Order
from . import constants


@login_required(login_url='user.login')
def cache_payment(request):
    payment_id = request.POST.get('razorpay_payment_id')
    amount = request.POST.get('amount')
    try:
        data = razorpay_client.payment.capture(payment_id, amount)
        # ragister_in_razorpay(data, request.user)

    except razorpay.errors.BadRequestError:
        pass  # todo do something bro
    cart = request.user.cart
    order = Order.objects.create(customer=request.user,
                                 cart=cart)
    cart.status = constants.FROZEN
    cart.save()
    # OrderStatusUpdate.objects.create(status='Order Placed', order=order)
    return redirect('home:home')


@login_required(login_url='user.login')
def orders_view(request, order_id=None):
    if order_id:
        try:
            order = Order.objects.get(customer=request.user, id=order_id)
            context = {'order': order, 'cart_products': order.cart.all_products()}
            return render(request, 'ecommerce/order.html', context=context)
        except Order.DoesNotExist:
            pass
    orders = Order.objects.filter(customer=request.user)
    context = {'orders': orders}
    context.update(default_context)
    return render(request, 'accounts/orders.html', context=context)


@login_required()
def wishlist_view(request):
    context = {}
    context.update(default_context)

    return render(request, 'ecommerce/wishlist.html')


def list_category(request, category_slug):
    try:
        category = Category.objects.get(slug=category_slug)
        context = {'products': ProductCategory.objects.filter(category=category)}
        context.update(default_context)
        return render(request, 'ecommerce/products_list.html', context=context)
    except Category.DoesNotExist:
        pass
#     todo add 404
