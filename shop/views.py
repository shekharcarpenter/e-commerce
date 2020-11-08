from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect

from shop.models import Product


# Create your views here.
def product_view(request, slug):
    product = Product.objects.get(slug=slug)
    quantity = 0
    if request.user and request.user.is_authenticated:
        cart_product = request.user.cart.all_products().filter(product=product).first()
        if cart_product:
            quantity = cart_product.quantity
    context = {'product': product, 'quantity': quantity}
    return render(request, 'ecommerce/product_view.html', context=context)


@login_required(login_url='user.login')
def add_to_cart(request):
    cart = request.user.cart
    product = Product.objects.get(id=int(request.POST.get('product_id')))
    cart.add_product(product, int(request.POST.get('quantity', 1)))
    return redirect('shop:view_product', slug=product.slug)
