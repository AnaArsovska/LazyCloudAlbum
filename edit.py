import webapp2
import models
import utils
import os
import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import images

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

class BuildHandler(blobstore_handlers.BlobstoreUploadHandler):
    @ndb.transactional
    def post(self):
        title = str(self.request.get('title')).strip()
        account = utils.get_account()
        album = models.Album( parent = account.key )
        if title :
            album.title = title

        if self.get_uploads():
            upload = self.get_uploads()[0]
            thumbnail_blob_key = upload.key()
            for upload in self.get_uploads():
                album.images.append(str(upload.key()))
        else:
            thumbnail_blob_key = None

        if thumbnail_blob_key:
            thumbnail_url = images.get_serving_url(thumbnail_blob_key, size=200, crop=True)
            album.thumbnail_url = thumbnail_url
            album.html = utils.vision_api_web_detection(self.get_uploads()[0])
        else:
            album.thumbnail_url = ""

        album.put()

        self.redirect('/')

class DeleteHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        album = utils.get_album_by_key(album_key)
        if album and album.key.parent().get().user_id == users.get_current_user().user_id():
            album.key.delete()
        self.redirect('/')

class EditHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        album = utils.get_album_by_key(album_key)
        title = str(self.request.get('title')).strip()
        if title :
            album.title = title
        album.public = bool(self.request.get("public"))
        album.put()
        self.redirect('/')

application = webapp2.WSGIApplication([
    (r'/edit/build', BuildHandler),
    (r'/edit/delete/(.*)', DeleteHandler),
    (r'/edit/(.*)', EditHandler)
    ], debug=True)
