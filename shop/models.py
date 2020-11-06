from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import models
from django.db.models import Exists, OuterRef
from django.template.defaultfilters import striptags
from django.urls import reverse
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
