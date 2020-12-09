from django.shortcuts import render

from shop.models import Product, Category


# Create your views here.
def home_view(request):
    products = Product.objects.all()
    context = {'products': products, 'product_categories':Category.objects.filter(is_public=True)}
    return render(request, 'home/index.html', context=context)
