from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=13)
    last_name = None
    first_name = None

    @property
    def cart(self):
        from shop.models import Cart, OPEN
        cart, created = Cart.objects.get_or_create(owner=self, status=OPEN)
        return cart

    @property
    def wish_list(self):
        from shop.models import Cart, SAVED
        cart, created = Cart.objects.get_or_create(owner=self, status=SAVED)
        return cart


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    house_number = models.CharField(max_length=20)
    full_name = models.CharField(max_length=255)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pin_code = models.CharField(max_length=50)
