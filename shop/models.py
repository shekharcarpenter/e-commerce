import uuid
import zlib
from datetime import datetime
from decimal import Decimal as D
from string import Template

import pytz
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import models
from django.template.defaultfilters import striptags
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from .fields import slugify


class Category(models.Model):
    name = models.CharField(_('Name'), max_length=255, db_index=True)
    description = models.TextField(_('Description'), blank=True)
    meta_title = models.CharField(_('Meta title'), max_length=255, blank=True, null=True)
    meta_description = models.TextField(_('Meta description'), blank=True, null=True)
    image = models.ImageField(_('Image'), upload_to='categories', blank=True,
                              null=True, max_length=255)
    slug = models.SlugField(_('Slug'), max_length=255, db_index=True)
    cat_uuid = models.UUIDField(null=True, blank=True, default=uuid.uuid4)
    is_public = models.BooleanField(
        _('Is public'),
        default=True,
        db_index=True,
        help_text=_("Show this category in search results and catalogue listings."))

    def __str__(self):
        return self.name

    @property
    def full_slug(self):
        """
        Returns a string of this category's slug concatenated with the slugs
        of it's ancestors, e.g. 'books/non-fiction/essential-programming'.
        Oscar used to store this as in the 'slug' model field, but this field
        has been re-purposed to only store this category's slug and to not
        include it's ancestors' slugs.
        """
        return self.generate_slug()

    def generate_slug(self):
        """
        Generates a slug for a category. This makes no attempt at generating
        a unique slug.
        """
        return slugify(self.name)

    def save(self, *args, **kwargs):
        """
        Oscar traditionally auto-generated slugs from names. As that is
        often convenient, we still do so if a slug is not supplied through
        other means. If you want to control slug creation, just create
        instances with a slug already set, or expose a field on the
        appropriate forms.
        """
        if not self.slug:
            self.slug = self.generate_slug()
        super().save(*args, **kwargs)

    def get_meta_title(self):
        return self.meta_title or self.name

    def get_meta_description(self):
        return self.meta_description or striptags(self.description)

    class Meta:
        app_label = 'shop'
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    @property
    def get_all_products(self):
        return ProductCategory.objects.filter(category=self)


class Occasion(models.Model):
    title = models.CharField(max_length=30)
    slug = models.SlugField()

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        self.slug = slugify(self.title)
        super().save()


class ProductImages(models.Model):
    """
        An image of a product
        """
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_("Product"))
    original = models.ImageField(
        _("Original"), upload_to='product', max_length=255)
    caption = models.CharField(_("Caption"), max_length=200, blank=True)

    #: Use display_order to determine which is the "primary" image
    display_order = models.PositiveIntegerField(
        _("Display order"), default=0, db_index=True,
        help_text=_("An image with a display order of zero will be the primary"
                    " image for a product"))
    date_created = models.DateTimeField(_("Date created"), auto_now_add=True)

    # from colorfield.fields import ColorField
    # color = ColorField(null=True, blank=True)

    class Meta:
        app_label = 'shop'
        # Any custom models should ensure that this ordering is unchanged, or
        # your query count will explode. See AbstractProduct.primary_image.
        ordering = ["display_order"]
        verbose_name = _('Product image')
        verbose_name_plural = _('Product images')

    def __str__(self):
        return "Image of '%s'" % self.product

    def is_primary(self):
        """
        Return bool if image display order is 0
        """
        return self.display_order == 0

    def delete(self, *args, **kwargs):
        """
        Always keep the display_order as consecutive integers. This avoids
        issue #855.
        """
        super().delete(*args, **kwargs)
        for idx, image in enumerate(self.product.images.all()):
            image.display_order = idx
            image.save()


# Create your models here.
class Product(models.Model):
    name = models.CharField(_('Name'), max_length=128)
    slug = models.SlugField(_('Slug'), max_length=255, unique=False)
    actual_price = models.PositiveIntegerField()
    discounted_price = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(_('Description'), blank=True)

    sku = models.CharField(max_length=20)
    material = models.CharField(max_length=100, null=True, blank=True)
    fabrics = models.CharField(max_length=100, null=True, blank=True)
    fit_type = models.CharField(max_length=100, null=True, blank=True)
    fabric_composition = models.CharField(max_length=100, null=True, blank=True)
    model_height = models.CharField(max_length=100, null=True, blank=True)
    tags = models.TextField()

    is_public = models.BooleanField(
        _('Is public'),
        default=True,
        db_index=True,
        help_text=_("Show this product in search results and catalogue listings."))
    recommended_products = models.ManyToManyField(
        'shop.Product', through='ProductRecommendation', blank=True,
        verbose_name=_("Recommended products"),
        help_text=_("These are products that are recommended to accompany the "
                    "main product."))
    rating = models.FloatField(_('Rating'), null=True, editable=False)
    date_created = models.DateTimeField(
        _("Date created"), auto_now_add=True, db_index=True)

    # This field is used by Haystack to reindex search
    date_updated = models.DateTimeField(
        _("Date updated"), auto_now=True, db_index=True)

    categories = models.ManyToManyField(
        'shop.Category', through='ProductCategory',
        verbose_name=_("Categories"))

    is_discountable = models.BooleanField(
        _("Is discountable?"), default=True, help_text=_(
            "This flag indicates if this product can be used in an offer "
            "or not"))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.get_title())
        super().save(*args, **kwargs)
        # self.attr.save()

    def __str__(self):
        return self.name

    @property
    def price(self):
        return self.discounted_price if self.discounted_price else self.actual_price

    @property
    def has_stockrecords(self):
        """
        Test if this product has any stockrecords
        """
        return self.stockrecords.exists()

    @property
    def num_stockrecords(self):
        return self.stockrecords.count()

    def get_all_images(self):
        return ProductImages.objects.filter(product=self)

    def all_images(self):
        return self.get_all_images()

    def primary_image(self):
        """
        Returns the primary image for a product. Usually used when one can
        only display one product image, e.g. in a list of products.
        """
        return self.get_all_images().first()

    def calculate_rating(self):
        from django.db.models import Sum, Count
        """
        Calculate rating value
        """
        result = self.reviews.filter(
            status=self.reviews.model.APPROVED
        ).aggregate(
            sum=Sum('score'), count=Count('id'))
        reviews_sum = result['sum'] or 0
        reviews_count = result['count'] or 0
        rating = None
        if reviews_count > 0:
            rating = float(reviews_sum) / reviews_count
        return rating

    def has_review_by(self, user):
        if user.is_anonymous:
            return False
        return self.reviews.filter(user=user).exists()

    def update_rating(self):
        """
        Recalculate rating field
        """
        self.rating = self.calculate_rating()
        self.save()


class ProductCategory(models.Model):
    """
    Joining model between products and categories. Exists to allow customising.
    """
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        verbose_name=_("Product"))
    category = models.ForeignKey(
        'shop.Category',
        on_delete=models.CASCADE,
        verbose_name=_("Category"))

    class Meta:
        app_label = 'shop'
        ordering = ['product', 'category']
        unique_together = ('product', 'category')
        verbose_name = _('Product category')
        verbose_name_plural = _('Product categories')

    def __str__(self):
        return "<productcategory for product '%s'>" % self.product


class ProductOccasion(models.Model):
    """
    Joining model between products and categories. Exists to allow customising.
    """
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        verbose_name=_("Product"))
    occasion = models.ForeignKey(
        'shop.Occasion',
        on_delete=models.CASCADE,
        verbose_name=_("Occasion"))

    class Meta:
        app_label = 'shop'
        ordering = ['product', 'occasion']
        unique_together = ('product', 'occasion')
        verbose_name = _('Product Occasion')
        verbose_name_plural = _('Product Occasions')

    # def __str__(self):
    #     return "<productcategory for product '%s'>" % self.product


class ProductRecommendation(models.Model):
    """
    'Through' model for product recommendations
    """
    primary = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        related_name='primary_recommendations',
        verbose_name=_("Primary product"))
    recommendation = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        verbose_name=_("Recommended product"))
    ranking = models.PositiveSmallIntegerField(
        _('Ranking'), default=0, db_index=True,
        help_text=_('Determines order of the products. A product with a higher'
                    ' value will appear before one with a lower ranking.'))

    class Meta:
        app_label = 'shop'
        ordering = ['primary', '-ranking']
        unique_together = ('primary', 'recommendation')
        verbose_name = _('Product recommendation')
        verbose_name_plural = _('Product recomendations')


OPEN, MERGED, SAVED, FROZEN, SUBMITTED = (
    "Open", "Merged", "Saved", "Frozen", "Submitted")


class Cart(models.Model):
    """
    cart object
    """
    # carts can be anonymously owned - hence this field is nullable.  When a
    # anon user signs in, their two carts are merged.
    owner = models.ForeignKey(
        'users.User',
        null=True,
        related_name='carts',
        on_delete=models.CASCADE,
        verbose_name=_("Owner"))

    # cart statuses
    # - Frozen is for when a cart is in the process of being submitted
    #   and we need to prevent any changes to it.
    STATUS_CHOICES = (
        (OPEN, _("Open - currently active")),
        (SAVED, _("Saved - for items to be purchased later")),
        (FROZEN, _("Frozen - the cart cannot be modified")),
        (SUBMITTED, _("Submitted - has been ordered at the checkout")),
    )
    status = models.CharField(
        _("Status"), max_length=128, default=OPEN, choices=STATUS_CHOICES)

    # A cart can have many vouchers attached to it.  However, it is common
    # for sites to only allow one voucher per cart - this will need to be
    # enforced in the project's codebase.
    # vouchers = models.ManyToManyField(
    #     'voucher.Voucher', verbose_name=_("Vouchers"), blank=True)

    date_created = models.DateTimeField(_("Date created"), auto_now_add=True)
    date_merged = models.DateTimeField(_("Date merged"), null=True, blank=True)
    date_submitted = models.DateTimeField(_("Date submitted"), null=True,
                                          blank=True)

    # Only if a cart is in one of these statuses can it be edited
    editable_statuses = (OPEN, SAVED)

    class Meta:
        app_label = 'shop'
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')

    # objects = models.Manager()

    # open = OpencartManager()
    # saved = SavedcartManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # We keep a cached copy of the cart products as we refer to them often
        # within the same request cycle.  Also, applying offers will append
        # discount data to the cart products which isn't persisted to the DB and
        # so we want to avoid reloading them as this would drop the discount
        # information.
        self._products = None
        # self.offer_applications = OfferApplications()

    def __str__(self):
        return _(
            "%(status)s cart (owner: %(owner)s, products: %(num_products)d)") \
               % {'status': self.status,
                  'owner': self.owner,
                  'num_products': self.num_products}

    def add_product(self, product, quantity=1):
        entry, created = self.products.get_or_create(cart=self, product=product)
        if not created:
            entry.quantity = quantity
            entry.save()

    @property
    def quantity(self):
        return self.all_products().count()

    @property
    def total_price(self):
        return sum([product.price for product in self.all_products()])

    @property
    def total_price_in_paise(self):
        return sum([product.price for product in self.all_products()]) * 100

    @property
    def can_be_edited(self):
        return self.status in self.editable_statuses

    # ========
    # Strategy
    # ========

    def all_products(self):
        """
        Return a cached set of cart products.
        This is important for offers as they alter the line models and you
        don't want to reload them from the DB as that information would be
        lost.
        """
        if self.id is None:
            return self.products.none()
        if self._products is None:
            self._products = (
                self.products
                    .select_related('product')
                    # .prefetch_related(
                    # 'attributes', 'product__images')
                    .order_by(self._meta.pk.name))
        return self._products

    @property
    def productss(self):
        """
        Return a cached set of cart products.
        This is important for offers as they alter the line models and you
        don't want to reload them from the DB as that information would be
        lost.
        """
        if self.id is None:
            return self.products.none()
        if self._products is None:
            self._products = (
                self.products
                    .select_related('product')
                    # .prefetch_related(
                    # 'attributes', 'product__images')
                    .order_by(self._meta.pk.name))
        return self._products

    # ============
    # Manipulation
    # ============

    def flush(self):
        """
        Remove all products from cart.
        """
        if self.status == self.FROZEN:
            raise PermissionDenied("A frozen cart cannot be flushed")
        self.products.all().delete()
        self._products = None

    def freeze(self):
        """
        Freezes the cart so it cannot be modified.
        """
        self.status = self.FROZEN
        self.save()

    freeze.alters_data = True

    def thaw(self):
        """
        Unfreezes a cart so it can be modified again
        """
        self.status = self.OPEN
        self.save()

    thaw.alters_data = True

    def submit(self):
        """
        Mark this cart as submitted
        """
        self.status = self.SUBMITTED
        self.date_submitted = now()
        self.save()

    submit.alters_data = True

    # Kept for backwards compatibility
    set_as_submitted = submit

    def is_shipping_required(self):
        """
        Test whether the cart contains physical products that require
        shipping.
        """
        for line in self.all_products():
            if line.product.is_shipping_required:
                return True
        return False

    # =======
    # Helpers
    # =======

    def _create_line_reference(self, product, stockrecord, options):
        """
        Returns a reference string for a line based on the item
        and its options.
        """
        base = '%s_%s' % (product.id, stockrecord.id)
        if not options:
            return base
        repr_options = [{'option': repr(option['option']),
                         'value': repr(option['value'])} for option in options]
        return "%s_%s" % (base, zlib.crc32(repr(repr_options).encode('utf8')))

    def _get_total(self, property):
        """
        For executing a named method on each line of the cart
        and returning the total.
        """
        total = D('0.00')
        for line in self.all_products():
            try:
                total += getattr(line, property)
            except ObjectDoesNotExist:
                # Handle situation where the product may have been deleted
                pass
            except TypeError:
                # Handle Unavailable products with no known price
                info = self.get_stock_info(line.product, line.attributes.all())
                if info.availability.is_available_to_buy:
                    raise
                pass
        return total

    # ==========
    # Properties
    # ==========

    @property
    def is_empty(self):
        """
        Test if this cart is empty
        """
        return self.id is None or self.num_products == 0

    @property
    def total_discount(self):
        return self._get_total('discount_value')

    @property
    def total_excl_tax_excl_discounts(self):
        """
        Return total price excluding tax and discounts
        """
        return self._get_total('line_price_excl_tax')

    @property
    def num_products(self):
        """Return number of products"""
        return self.all_products().count()

    @property
    def num_items(self):
        """Return number of items"""
        return sum(line.quantity for line in self.products.all())

    @property
    def num_items_without_discount(self):
        num = 0
        for line in self.all_products():
            num += line.quantity_without_discount
        return num

    @property
    def num_items_with_discount(self):
        num = 0
        for line in self.all_products():
            num += line.quantity_with_discount
        return num

    @property
    def time_before_submit(self):
        if not self.date_submitted:
            return None
        return self.date_submitted - self.date_created

    @property
    def time_since_creation(self, test_datetime=None):
        if not test_datetime:
            test_datetime = now()
        return test_datetime - self.date_created

    @property
    def is_submitted(self):
        return self.status == self.SUBMITTED

    @property
    def can_be_edited(self):
        """
        Test if a cart can be edited
        """
        return self.status in self.editable_statuses


class CartProduct(models.Model):
    cart = models.ForeignKey(
        'shop.Cart',
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name=_("Cart"))

    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        related_name='cart_product',
        verbose_name=_("Product"))

    quantity = models.PositiveIntegerField(_('Quantity'), default=1)

    # Track date of first addition
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True, db_index=True)
    date_updated = models.DateTimeField(_("Date Updated"), auto_now=True, db_index=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        app_label = 'shop'
        ordering = ['date_created', 'pk']
        unique_together = ("cart", "product")
        verbose_name = _('Cart Product')
        verbose_name_plural = _('Cart Product')

    def __str__(self):
        return _(
            "cart #%(cart_id)d, Product #%(product_id)d, quantity"
            " %(quantity)d") % {'cart_id': self.cart.pk,
                                'product_id': self.product.pk,
                                'quantity': self.quantity}

    def save(self, *args, **kwargs):
        if not self.cart.can_be_edited:
            raise PermissionDenied(
                _("You cannot modify a %s cart") % (
                    self.cart.status.lower(),))
        return super().save(*args, **kwargs)

    @property
    def price(self):
        return self.product.price * self.quantity


from . import constants


class Order(models.Model):
    ORDER_STATUS_CHOICES = (
        (constants.TO_BE_SHIPPED, 'Shipping Pending'),
        (constants.SHIPPED, 'Shipped'),
        (constants.CANCELED, 'Cancelled'),
        (constants.DELIVERED, 'Delivered')
    )
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE)
    status = models.CharField(choices=ORDER_STATUS_CHOICES, max_length=2, default=constants.TO_BE_SHIPPED)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def status_text(self):
        return dict(self.ORDER_STATUS_CHOICES)[int(self.status)]

    class Meta:
        ordering = ('-created_at',)


class DeltaTemplate(Template):
    delimiter = "%"


def strfdelta(tdelta, fmt):
    d = {"D": tdelta.days}
    d["H"], rem = divmod(tdelta.seconds, 3600)
    d["M"], d["S"] = divmod(rem, 60)
    t = DeltaTemplate(fmt)
    return t.substitute(**d)


class DealOfDay(models.Model):
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE)
    date = models.DateField()

    @property
    def end_time(self):
        return datetime.combine(self.date, datetime.max.time()).replace(tzinfo=pytz.timezone("Asia/Calcutta"))

    @property
    def remaining_time(self):
        return self.end_time - timezone.now() if self.end_time > timezone.now() else None

    @property
    def remaining_hours(self):
        hour, minutes = strfdelta(self.remaining_time, "%H,%M").split(',')
        return hour

    @property
    def remaining_minutes(self):
        hour, minutes = strfdelta(self.remaining_time, "%H,%M").split(',')
        return minutes
