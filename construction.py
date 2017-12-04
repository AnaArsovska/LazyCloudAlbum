import webapp2
import utils
import logging


from google.appengine.api import images
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.blobstore import BlobKey

class Construct(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        logging.info(utils.get_album_by_key(album_key).title)
        #utils.send_album_email("mrgnmcsmith@gmail.com", "Album")

application = webapp2.WSGIApplication([(r'/construction', Construct)], debug=True)
