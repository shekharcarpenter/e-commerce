from django.shortcuts import render

from shop.models import Product


# Create your views here.
def home_view(request):
    products = Product.objects.all()
    context = {'products': products}
    return render(request, 'home/index.html', context=context)
