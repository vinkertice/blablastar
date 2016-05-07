from collections import defaultdict
from datetime import datetime, timedelta
import logging
from random import getrandbits

from google.appengine.ext import ndb, blobstore
from google.appengine.api.memcache import Client
from google.appengine.api.images import Image, JPEG, get_serving_url, delete_serving_url

import cloudstorage as gcs

bbs_memcache = Client()


class Location(ndb.Model):
    """ Location in the galaxy to depart or arrive to: Planet, Star, City """
    name = ndb.StringProperty(required=True)
    parent_location = ndb.KeyProperty()

    all_cache_key = 'all_locations'

    @classmethod
    def save_from_request(cls, request):
        location = cls(id=request.get('name'), name=request.get('name'))
        parent = request.get('parent')
        if parent:  # in case we ever pass a parent location
            location.parent_location = ndb.Key(cls, parent)
        location.put()

    @classmethod
    def get_all(cls):
        """ Return all memcached locations """
        locations = bbs_memcache.get(cls.all_cache_key)
        if locations is None:
            locations = cls().query().fetch()
            bbs_memcache.set(cls.all_cache_key, locations)
            logging.info("{} locations saved to memcache".format(len(locations)))
        return locations

    @classmethod
    def _clear_all_memcache(cls):
        logging.info("Removing locations from memcache")
        bbs_memcache.delete(cls.all_cache_key)

    def _post_put_hook(self, future):
        self._clear_all_memcache()

    @classmethod
    def _post_delete_hook(cls, key, future):
        cls._clear_all_memcache()


class StarTrip(ndb.Model):
    """ Trip across the galaxy from one origin to a destination """
    description = ndb.TextProperty(required=True)
    origin = ndb.KeyProperty(required=True)
    destiny = ndb.KeyProperty(required=True)
    date = ndb.DateProperty(required=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    available_seats = ndb.IntegerProperty(default=1)
    booked_seats = ndb.IntegerProperty(default=0)
    pilot_name = ndb.StringProperty()
    price = ndb.IntegerProperty(default=0)  # in Galactic Credits

    @classmethod
    def save_from_request(cls, request):
        """ Save trip from http request parameters """
        star_trip = cls()
        star_trip.date = datetime.strptime(request.get('date'), '%Y-%m-%d')
        star_trip.description = request.get('description')
        star_trip.available_seats = int(request.get('seats'))
        star_trip.pilot_name = request.get('pilot')
        star_trip.origin = ndb.Key(Location, request.get('origin'))
        star_trip.destiny = ndb.Key(Location, request.get('destiny'))
        star_trip.price = int(request.get('price'))
        star_trip.put()

    @classmethod
    def query_from_request(cls, request, limit=10):
        """ TODO: pagination (cursors) """
        try:
            origin = ndb.Key(Location, request.get('origin'))
            destiny = ndb.Key(Location, request.get('destiny'))
            date = datetime.strptime(request.get('date'), '%Y-%m-%d').date()
        except:
            origin = destiny = date = None
        if origin and destiny and date:
            result = cls.query(cls.origin == origin, cls.destiny == destiny, cls.date == date
                               ).order(-cls.date).fetch(limit)
        else:
            result = cls.query().order(-cls.date).fetch(limit)
        params = {'searched_origin': origin, 'searched_destiny': destiny, 'searched_date': date}
        return result, params


class SpaceShip(ndb.Model):
    """ Space ship with a name and a picture """
    name = ndb.StringProperty(required=True)
    model = ndb.StringProperty()
    description = ndb.TextProperty()
    image_gcs_key = ndb.StringProperty()

    @classmethod
    def save_from_request(cls, request, image_blob):
        image_gcs_key = cls.store_picture_from_content(image_blob.key())

        ship = cls(id=request.get('name'), name=request.get('name'),
                   model=request.get('model'), description=request.get('description'),
                   image_gcs_key=image_gcs_key)
        ship.put()
        logging.info("Stored {}".format(ship.key))

    @classmethod
    def store_picture_from_content(cls, blob_key):
        """ Resize picture and upload to Cloud Storage bucket. Return the GCS key """
        data = blobstore.BlobReader(blob_key).read()
        img = Image(data)
        img.resize(width=800, height=600)
        # img.im_feeling_lucky()
        img = img.execute_transforms(output_encoding=JPEG)

        new_gcs_key = cls.upload_blob_to_gcs(img, content_type='img/jpeg')

        # delete original blob
        delete_serving_url(blob_key)
        blobstore.delete(blob_key)

        return new_gcs_key

    @staticmethod
    def upload_blob_to_gcs(data, filename=None, bucket='/spaceships/', content_type='img/jpg', options=None):
        """ Upload a blob to Google Cloud Storage and return its new blob key """
        filename = filename or "%032x" % getrandbits(128)
        options = options or {'x-goog-acl': 'public-read'}
        with gcs.open(bucket + filename, 'w',
                      content_type=content_type,
                      options=options) as output:
            output.write(data)
        # Blobstore API requires extra /gs to distinguish against blobstore files.
        gs_key = blobstore.create_gs_key('/gs' + bucket + filename)
        logging.info("GCS File {} created, key={}".format(filename, gs_key))
        return gs_key

    @property
    def image_url(self):
        return get_serving_url(self.image_gcs_key)


class TopLocations(ndb.Model):
    """ Rollup model to save the most frequent destinations in the Galaxy """
    destinations = ndb.KeyProperty(repeated=True)
    origins = ndb.KeyProperty(repeated=True)
    instance_id = '1'

    @classmethod
    def run(cls, limit=5, days=5):
        """ Run rollup: get the top 5 destinations and origins of the
            last 5 days
        """
        today = datetime.today()
        t1 = today - timedelta(days=days)
        query = StarTrip.query(StarTrip.date > t1)
        origins = defaultdict(int)
        destinations = defaultdict(int)
        for trip in query.iter():
            origins[trip.origin] += 1
            destinations[trip.destiny] += 1
        top_origins = sorted(origins.items(), key=lambda t: t[1], reverse=True)[:limit]
        top_destinations = sorted(origins.items(), key=lambda t: t[1], reverse=True)[:limit]

        top_locs = cls(id=cls.instance_id, origins=[o[0] for o in top_origins],
                       destinations=[d[0] for d in top_destinations])
        top_locs.put()
        logging.info("Top Locations saved: {}".format(top_locs))

