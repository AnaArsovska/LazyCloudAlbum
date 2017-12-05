import webapp2
import utils
import logging

from google.appengine.api import images
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.blobstore import BlobKey
from PIL import Image

class Construct(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        user = album.key.parent().get()
        logging.info(utils.get_album_by_key(album_key).title)
        ratio = {}
        for image_file in album.images:
            img = Image.open(blobstore.BlobReader(image_file))
            (w, h) = img.size
            logging.info(h)
            ratio[image_file] = float(h)/float(w)
        logging.info(ratio)
        logging.info(album.title)

        account = album.key.parent().get()
        html = utils.generate_dummy_html(account, album.key.urlsafe(), album.images)
        filename = utils.get_html_filename(account, album.key.urlsafe())
        utils.upload_text_file_to_cloudstorage(filename, html)
        #utils.send_album_email("mrgnmcsmith@gmail.com", "Album")

class Delete(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        utils.clear_album_data(album)
        album.key.delete()

application = webapp2.WSGIApplication([(r'/construction', Construct), (r'/delete', Delete) ], debug=True)
