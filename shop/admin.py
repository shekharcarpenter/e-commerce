from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Product, Category, ProductRecommendation, ProductImages


class ProductRecommendationInline(admin.TabularInline):
    model = ProductRecommendation
    fk_name = 'primary'
    raw_id_fields = ['primary', 'recommendation']


class ProductImageInline(admin.TabularInline):
    model = ProductImages
    # fk_name = 'primary'
    # raw_id_fields = ['primary', 'recommendation']


class ProductAdmin(admin.ModelAdmin):
    date_hierarchy = 'date_created'
    list_display = ('name', 'price', 'sku', 'date_created')
    list_filter = ['is_discountable']
    inlines = [ProductImageInline, ProductRecommendationInline]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ['sku', 'name']


class CategoryAdmin(TreeAdmin):
    form = movenodeform_factory(Category)
    list_display = ('name', 'slug')


admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
