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

app_name = 'users'
urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('my-account', views.my_account, name='my_account'),
    path('register', views.register_view, name='register'),
    path('address', views.address_view, name='address'),
    path('address/<int:pk>', views.address_view, name='address'),
    path('add-address', views.add_address, name='add_address'),
    path('delete-address/<int:pk>', views.delete_address, name='delete-address'),
]
