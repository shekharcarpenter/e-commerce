import zlib
from decimal import Decimal as D

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import models
from django.db.models import Exists, OuterRef
from django.template.defaultfilters import striptags
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from .fields import slugify


class Category(MP_Node):
    """
    A product category. Merely used for navigational purposes; has no
    effects on business logic.
    Uses :py:mod:`django-treebeard`.
    """
    #: Allow comparison of categories on a limited number of fields by ranges.
    #: When the Category model is overwritten to provide CMS content, defining
    #: this avoids fetching a lot of unneeded extra data from the database.
    COMPARISON_FIELDS = ('pk', 'path', 'depth')

    name = models.CharField(_('Name'), max_length=255, db_index=True)
    description = models.TextField(_('Description'), blank=True)
    meta_title = models.CharField(_('Meta title'), max_length=255, blank=True, null=True)
    meta_description = models.TextField(_('Meta description'), blank=True, null=True)
    image = models.ImageField(_('Image'), upload_to='categories', blank=True,
                              null=True, max_length=255)
    slug = models.SlugField(_('Slug'), max_length=255, db_index=True)

    is_public = models.BooleanField(
        _('Is public'),
        default=True,
        db_index=True,
        help_text=_("Show this category in search results and catalogue listings."))

    ancestors_are_public = models.BooleanField(
        _('Ancestor categories are public'),
        default=True,
        db_index=True,
        help_text=_("The ancestors of this category are public"))

    _slug_separator = '/'
    _full_name_separator = ' > '

    # objects = CategoryQuerySet.as_manager()

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """
        Returns a string representation of the category and it's ancestors,
        e.g. 'Books > Non-fiction > Essential programming'.
        It's rarely used in Oscar, but used to be stored as a CharField and is
        hence kept for backwards compatibility. It's also sufficiently useful
        to keep around.
        """
        names = [category.name for category in self.get_ancestors_and_self()]
        return self._full_name_separator.join(names)

    def get_full_slug(self, parent_slug=None):
        if self.is_root():
            return self.slug

        cache_key = self.get_url_cache_key()
        full_slug = cache.get(cache_key)
        if full_slug is None:
            parent_slug = parent_slug if parent_slug is not None else self.get_parent().full_slug
            full_slug = "%s%s%s" % (parent_slug, self._slug_separator, self.slug)
            cache.set(cache_key, full_slug)

        return full_slug

    @property
    def full_slug(self):
        """
        Returns a string of this category's slug concatenated with the slugs
        of it's ancestors, e.g. 'books/non-fiction/essential-programming'.
        Oscar used to store this as in the 'slug' model field, but this field
        has been re-purposed to only store this category's slug and to not
        include it's ancestors' slugs.
        """
        return self.get_full_slug()

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

    def set_ancestors_are_public(self):
        # Update ancestors_are_public for the sub tree.
        # note: This doesn't trigger a new save for each instance, rather
        # just a SQL update.
        included_in_non_public_subtree = self.__class__.objects.filter(
            is_public=False, path__rstartswith=OuterRef("path"), depth__lt=OuterRef("depth")
        )
        self.get_descendants_and_self().update(
            ancestors_are_public=Exists(
                included_in_non_public_subtree.values("id"), negated=True))

        # Correctly populate ancestors_are_public
        self.refresh_from_db()

    @classmethod
    def fix_tree(cls, destructive=False):
        super().fix_tree(destructive)
        for node in cls.get_root_nodes():
            # ancestors_are_public *must* be True for root nodes, or all trees
            # will become non-public
            if not node.ancestors_are_public:
                node.ancestors_are_public = True
                node.save()
            else:
                node.set_ancestors_are_public()

    def get_meta_title(self):
        return self.meta_title or self.name

    def get_meta_description(self):
        return self.meta_description or striptags(self.description)

    def get_ancestors_and_self(self):
        """
        Gets ancestors and includes itself. Use treebeard's get_ancestors
        if you don't want to include the category itself. It's a separate
        function as it's commonly used in templates.
        """
        if self.is_root():
            return [self]

        return list(self.get_ancestors()) + [self]

    def get_descendants_and_self(self):
        """
        Gets descendants and includes itself. Use treebeard's get_descendants
        if you don't want to include the category itself. It's a separate
        function as it's commonly used in templates.
        """
        return self.get_tree(self)

    def get_url_cache_key(self):
        current_locale = get_language()
        cache_key = 'CATEGORY_URL_%s_%s' % (current_locale, self.pk)
        return cache_key

    def _get_absolute_url(self, parent_slug=None):
        """
        Our URL scheme means we have to look up the category's ancestors. As
        that is a bit more expensive, we cache the generated URL. That is
        safe even for a stale cache, as the default implementation of
        ProductCategoryView does the lookup via primary key anyway. But if
        you change that logic, you'll have to reconsider the caching
        approach.
        """
        return reverse('catalogue:category', kwargs={
            'category_slug': self.get_full_slug(parent_slug=parent_slug), 'pk': self.pk
        })

    def get_absolute_url(self):
        return self._get_absolute_url()

    class Meta:
        app_label = 'shop'
        ordering = ['path']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def has_children(self):
        return self.get_num_children() > 0

    def get_num_children(self):
        return self.get_children().count()


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
    price = models.PositiveIntegerField()
    description = models.TextField(_('Description'), blank=True)

    sku = models.CharField(max_length=20)
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
