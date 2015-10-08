"""
This module defines the mapping between Datastore and Python objects.
"""
import StringIO
from caravel.storage import photos
from google.appengine.ext import db
import re
import inflect
INFLECT_ENGINE = inflect.engine()

class DerivedProperty(db.Property):
    """
    A DerivedProperty allows one to create a property that is computed on
    demand when saving a property.
    """

    def __init__(self, derive_func, *args, **kwargs):
        """Initialize this property given a derivation function."""
        super(DerivedProperty, self).__init__(*args, **kwargs)
        self.derive_func = derive_func

    def __get__(self, model_instance, model_class):
        """Override when this property is read from an entity."""
        if model_instance is None:
            return self
        return self.derive_func(model_instance)

    def __set__(self, model_instance, value):
        """Ignore assignment to entity.prop."""

class Versioned(db.Expando):
    version = db.IntegerProperty(default=1)
    migrations = {}

    def __init__(self, *vargs, **kwargs):
        """
        Ensure that version is set to SCHEMA_VERSION.
        """

        if 'version' not in kwargs:
            kwargs['version'] = self.__class__.SCHEMA_VERSION
        super(Versioned, self).__init__(*vargs, **kwargs)

    @classmethod
    def migration(kls, to_version):
        """
        Migrate to SCHEMA_VERSION.
        """

        def inner(func):
            kls.migrations = dict(kls.migrations)
            kls.migrations[to_version] = func
            return func
        return inner

    def migrate(self):
        while self.version < self.SCHEMA_VERSION:
            self.migrations.get(self.version, lambda _: None)(self)
            self.version += 1

def fold_query_term(word):
    """
    Returns the canonical representation of the given query word.
    """

    # if email do nothing:
    if "@" in word:
        return word

    # Else, singularize
    stripped = re.sub(r'[^a-z0-9]', '', word.lower())
    singularized = INFLECT_ENGINE.singular_noun(stripped) or stripped
    return singularized

class Listing(Versioned):
    SCHEMA_VERSION = 2
    CATEGORIES = [
        ("apartments", "Apartments"),
        ("subleases", "Subleases"),
        ("appliances", "Appliances"),
        ("bikes", "Bikes"),
        ("books", "Books"),
        ("cars", "Cars"),
        ("electronics", "Electronics"),
        ("employment", "Employment"),
        ("furniture", "Furniture"),
        ("miscellaneous", "Miscellaneous"),
        ("services", "Services"),
        ("wanted", "Wanted"),
    ]
    CATEGORIES_DICT = dict(CATEGORIES)

    seller = db.StringProperty() # an email address
    title = db.StringProperty(default="")
    body = db.TextProperty(default="")
    price = db.IntegerProperty(default=0) # in cents of a U.S. dollar
    posting_time = db.FloatProperty(default=0) # set to 0 iff not yet published
    categories = db.StringListProperty() # stored as keys of CATEGORIES
    admin_key = db.StringProperty() # how to administer this listing

    photos_ = db.StringListProperty(indexed=False, name="photos")
    thumbnails_ = db.StringListProperty(indexed=False, name="thumbnails")

    @property
    def permalink(self):
        return self.key().name()

    @property
    def primary_category(self):
        return (self.categories[:1] + ["miscellaneous"])[0]

    @DerivedProperty
    def keywords(self):
        """Generates keywords based on the alphanumeric words in the string."""

        # Tokenize title and body (ranking them equally)
        words = [self.seller] + self.title.split() + self.body.split()
        words += self.categories
        singularized = [fold_query_term(word) for word in words]

        # Return a uniqified list of words.
        return sorted(set(singularized[:500]) - set(['']))

    @property
    def photo_urls(self):
        """
        Gets the photo URLs for this listing.
        """

        return self.photos_

    @property
    def thumbnail_urls(self):
        """
        Gets the scaled photo URLs for this listing.
        """

        return self.thumbnails_

    @photo_urls.setter
    def photo_urls(self, url_or_fps):
        """
        Sets the URLs of the photos for this Listing.
        """

        large_photos, thumbnails = [], []

        for photo in url_or_fps:
            if not photo:
                continue

            if hasattr(photo, 'read'):
                photo = StringIO.StringIO(photo.read())
                large_photo = photos.upload(photo, 'large')
                photo.seek(0)
                thumbnail = photos.upload(photo, 'small')
            else:
                large_photo, thumbnail = photo, photo

            large_photos.append(large_photo)
            thumbnails.append(thumbnail)

        self.photos_, self.thumbnails_ = large_photos, thumbnails

@Listing.migration(1)
def from_single_thumbnail_to_many(listing):
    if hasattr(listing, "thumbnail_url") and listing.thumbnail_url:
        listing.thumbnails_ = [listing.thumbnail_url]