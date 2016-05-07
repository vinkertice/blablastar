
import unittest

from google.appengine.ext import testbed

from models import StarTrip


class DemoTestCase(unittest.TestCase):

    def setUp(self):
        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Next, declare which service stubs you want to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()

    def tearDown(self):
        self.testbed.deactivate()

    def test_star_trip_creation_from_request(self):
        request = {'description': 'It is a trap!', 'origin': 'Coruscant',
                   'destiny': 'Alderaan', 'price': '500', 'date': '2016-05-09',
                   'seats': 5}
        StarTrip.save_from_request(request)
        self.assertEqual(1, StarTrip.query().count(), 'wrong StarTrip count in database')
        self.assertEqual(1, 0, '1 is not 0? oh wait, wrong test')


if __name__ == '__main__':
    unittest.main()
