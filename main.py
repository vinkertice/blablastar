import logging

from google.appengine.ext.webapp import RequestHandler, WSGIApplication, template
from os.path import join, dirname


class OldHomeHandler(RequestHandler):
    """ Example of hardcoded HTML in response """
    def get(self):
        logging.info("In OldHomeHandler")
        self.response.write('<html>Hello <strong>world!</strong></html>')


class HomeHandler(RequestHandler):
    """ Example of template rendered controller with the same
        variable in the request and the response
    """
    def get(self):
        logging.info("In HomeHandler")
        x = self.request.get('x', 1)
        html = render('hello.html', {'x': x})
        self.response.write(html)


app = WSGIApplication([
    ('/old-home', OldHomeHandler),
    ('/.*', HomeHandler),
], debug=True)


def render(tmpl_file, values={}):
    path = join(dirname(__file__), 'templates', tmpl_file)
    return template.render(path, values)
