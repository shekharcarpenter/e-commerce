from django.shortcuts import render

from shop.models import Product, Category

default_context = {'categories': Category.objects.filter(is_public=True)}

# Create your views here.
def home_view(request):
    products = Product.objects.all()
    context = {'products': products, 'product_categories':Category.objects.filter(is_public=True)}
    context.update(default_context)
    print(context)
    return render(request, 'home/index.html', context=context)

def test_page(request):
    # products = Product.objects.all()
    # context = {'products': products, 'product_categories':Category.objects.filter(is_public=True)}
    return render(request, 'ecommerce/products_list.html')
