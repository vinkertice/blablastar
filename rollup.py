import logging

from google.appengine.ext.webapp import RequestHandler, WSGIApplication
from google.appengine.api.taskqueue import Task

from models import TopLocations


class RunRollupHandler(RequestHandler):
    def get(self):
        msg = "Starting Rollup of Top Locations"
        logging.info(msg)
        Task(url='/rollup/top_locations', target='rollup').add(queue_name='default')
        self.response.out.write(msg)

    def post(self):
        TopLocations.run()


app = WSGIApplication([
        ('/rollup/top_locations', RunRollupHandler),
], debug=True)