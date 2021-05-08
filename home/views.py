from django.shortcuts import render
from django.utils import timezone
from shop.models import Product, Category, DealOfDay

default_context = {'categories': Category.objects.filter(is_public=True)}


# Create your views here.
def home_view(request):
    products = Product.objects.all()
    context = {'products': products, 'product_categories': Category.objects.filter(is_public=True),
               'new_arrivals': Product.objects.filter(is_public=True).order_by('-date_created')[:20],
               'deals_of_the_day': DealOfDay.objects.filter(date=timezone.now().date())}
    context.update(default_context)
    print(context)
    return render(request, 'home/test-index.html', context=context)


def test_page(request):
    # products = Product.objects.all()
    # context = {'products': products, 'product_categories':Category.objects.filter(is_public=True)}
    return render(request, 'ecommerce/products_list.html')


def blog(request):
    return render(request, 'home/blog.html')


def about_us(request):
    return render(request, 'home/about-us.html')
