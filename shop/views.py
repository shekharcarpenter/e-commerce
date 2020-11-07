from django.shortcuts import render

from shop.models import Product


# Create your views here.
def product_view(request, slug):
    product = Product.objects.get(slug=slug)
    context = {'product': product}
    return render(request, 'ecommerce/product_view.html', context=context)
