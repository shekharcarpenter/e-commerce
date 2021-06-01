# from oscar.core.utils import slugify
import re

# from babel.dates import format_timedelta as format_td
from django.conf import settings
from django.db.models import SlugField as DjangoSlugField
from django.utils.encoding import force_str
from django.utils.module_loading import import_string

SLUGIFY_RE = re.compile(r'[^\w\s-]', re.UNICODE)


def slugify(value):
    """
    Slugify a string

    The OSCAR_SLUG_FUNCTION can be set with a dotted path to the slug
    function to use, defaults to 'oscar.core.utils.default_slugifier'.

    OSCAR_SLUG_MAP can be set of a dictionary of target:replacement pairs

    OSCAR_SLUG_BLACKLIST can be set to a iterable of words to remove after
    the slug is generated; though it will not reduce a slug to zero length.
    """
    value = str(value)

    # Re-map some strings to avoid important characters being stripped.  Eg
    # remap 'c++' to 'cpp' otherwise it will become 'c'.
    for k, v in settings.OSCAR_SLUG_MAP.items():
        value = value.replace(k, v)

    slugifier = import_string(settings.OSCAR_SLUG_FUNCTION)
    slug = slugifier(value, allow_unicode=settings.OSCAR_SLUG_ALLOW_UNICODE)

    # Remove stopwords from slug
    for word in settings.OSCAR_SLUG_BLACKLIST:
        slug = slug.replace(word + '-', '')
        slug = slug.replace('-' + word, '')

    return slug


class SlugField(DjangoSlugField):
    def __init__(self, *args, **kwargs):
        # not override parameter if it was passed explicitly,
        # so passed parameters takes precedence over the setting
        # if settings.OSCAR_SLUG_ALLOW_UNICODE:
        #     kwargs.setdefault('allow_unicode', settings.OSCAR_SLUG_ALLOW_UNICODE)

        super().__init__(*args, **kwargs)


class AutoSlugField(SlugField):
    """ AutoSlugField
    By default, sets editable=False, blank=True.
    Required arguments:
    populate_from
        Specifies which field or list of fields the slug is populated from.
    Optional arguments:
    separator
        Defines the used separator (default: '-')
    overwrite
        If set to True, overwrites the slug on every save (default: False)
    Inspired by SmileyChris' Unique Slugify snippet:
    http://www.djangosnippets.org/snippets/690/
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('blank', True)
        kwargs.setdefault('editable', False)

        populate_from = kwargs.pop('populate_from', None)
        if populate_from is None:
            raise ValueError("missing 'populate_from' argument")
        else:
            self._populate_from = populate_from
            self._populate_from_org = populate_from
        self.separator = kwargs.pop('separator', '-')
        self.overwrite = kwargs.pop('overwrite', False)
        self.uppercase = kwargs.pop('uppercase', False)
        self.allow_duplicates = kwargs.pop('allow_duplicates', False)

        # not override parameter if it was passed explicitly,
        # so passed parameters takes precedence over the setting
        # if settings.OSCAR_SLUG_ALLOW_UNICODE:
        #     kwargs.setdefault('allow_unicode', settings.OSCAR_SLUG_ALLOW_UNICODE)

        super().__init__(*args, **kwargs)

    def _slug_strip(self, value):
        """
        Cleans up a slug by removing slug separator characters that occur at
        the beginning or end of a slug.
        If an alternate separator is used, it will also replace any instances
        of the default '-' separator with the new separator.
        """
        re_sep = '(?:-|%s)' % re.escape(self.separator)
        value = re.sub('%s+' % re_sep, self.separator, value)
        return re.sub(r'^%s+|%s+$' % (re_sep, re_sep), '', value)

    def get_queryset(self, model_cls, slug_field):
        # https://github.com/django-extensions/django-extensions/pull/854/files
        for field in model_cls._meta._get_fields():
            if field == slug_field:
                return field.model._default_manager.all()
        return model_cls._default_manager.all()

    def slugify_func(self, content):
        if content:
            return slugify(content)
        return ''

    def create_slug(self, model_instance, add):  # NOQA (too complex)
        # get fields to populate from and slug field to set
        if not isinstance(self._populate_from, (list, tuple)):
            self._populate_from = (self._populate_from,)
        slug_field = model_instance._meta.get_field(self.attname)

        # only set slug if empty and first-time save, or when overwrite=True
        if add and not getattr(model_instance, self.attname) or self.overwrite:
            # slugify the original field content and set next step to 2
            def slug_for_field(field):
                return self.slugify_func(getattr(model_instance, field))

            slug = self.separator.join(map(slug_for_field, self._populate_from))  # NOQA
            next = 2
        else:
            # get slug from the current model instance
            slug = getattr(model_instance, self.attname)
            # model_instance is being modified, and overwrite is False,
            # so instead of doing anything, just return the current slug
            return slug

        # strip slug depending on max_length attribute of the slug field
        # and clean-up
        slug_len = slug_field.max_length
        if slug_len:
            slug = slug[:slug_len]
        slug = self._slug_strip(slug)

        if self.uppercase:
            slug = slug.upper()

        original_slug = slug

        if self.allow_duplicates:
            return slug

        # exclude the current model instance from the queryset used in finding
        # the next valid slug
        queryset = self.get_queryset(model_instance.__class__, slug_field)
        if model_instance.pk:
            queryset = queryset.exclude(pk=model_instance.pk)

        # form a kwarg dict used to impliment any unique_together contraints
        kwargs = {}
        for params in model_instance._meta.unique_together:
            if self.attname in params:
                for param in params:
                    kwargs[param] = getattr(model_instance, param, None)
        kwargs[self.attname] = slug

        # increases the number while searching for the next valid slug
        # depending on the given slug, clean-up
        while not slug or queryset.filter(**kwargs):
            slug = original_slug
            end = '%s%s' % (self.separator, next)
            end_len = len(end)
            if slug_len and len(slug) + end_len > slug_len:
                slug = slug[:slug_len - end_len]
                slug = self._slug_strip(slug)
            slug = '%s%s' % (slug, end)
            kwargs[self.attname] = slug
            next += 1
        return slug

    def pre_save(self, model_instance, add):
        value = force_str(self.create_slug(model_instance, add))
        setattr(model_instance, self.attname, value)
        return value

    def get_internal_type(self):
        return "SlugField"

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['populate_from'] = self._populate_from_org
        if not self.separator == '-':
            kwargs['separator'] = self.separator
        if self.overwrite is not False:
            kwargs['overwrite'] = True
        if self.allow_duplicates is not False:
            kwargs['allow_duplicates'] = True
        return name, path, args, kwargs
