from django.contrib import admin

from .models import Product, Category, ProductRecommendation, ProductImages, ProductCategory, DealOfDay


class ProductRecommendationInline(admin.TabularInline):
    model = ProductRecommendation
    fk_name = 'primary'
    raw_id_fields = ['primary', 'recommendation']


class CategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImages
    # fk_name = 'primary'
    # raw_id_fields = ['primary', 'recommendation']


class ProductAdmin(admin.ModelAdmin):
    date_hierarchy = 'date_created'
    list_display = ('name', 'price', 'sku', 'date_created')
    list_filter = ['is_discountable']
    inlines = [ProductImageInline, ProductRecommendationInline, CategoryInline]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ['sku', 'name']


class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}

    list_display = ('name', 'slug')


admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(DealOfDay)
