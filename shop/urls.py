"""Ecommerce URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path

from . import views

app_name = 'shop'
urlpatterns = [
    path('add-to-cart', views.add_to_cart, name='add_to_cart'),
    path('add-to-wish-list', views.add_to_wishlist, name='add_to_wish_list'),
    path('cart', views.cart_view, name='cart'),
    path('cart-delete/<int:id>', views.cart_delete, name='cart-delete'),
    path('checkout', views.checkout, name='checkout'),
    path('cache_payment', views.cache_payment, name='cache_payment'),
    path('orders', views.orders_view, name='orders_view'),
    path('orders/<int:order_id>', views.orders_view, name='orders_view'),
    path('wishlist', views.wishlist_view, name='wishlist_view'),
    path('wishlist-delete/<int:id>', views.wishlist_delete, name='wishlist-delete'),
    path('category/<str:category_slug>', views.list_category, name='list_category'),
    path('<str:slug>', views.product_view, name='view_product'),
    path('new_arrival/', views.new_arrival, name='new_arrival'),
    path('page404/', views.Page404, name='page404'),
]
