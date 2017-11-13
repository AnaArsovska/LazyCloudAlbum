import webapp2
import models
import utils
import os

from google.appengine.api import app_identity
from google.appengine.ext import ndb
from google.appengine.api import users

class BuildHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        title = str(self.request.get('title')).strip()
        account = utils.get_account()
        album = models.Album( parent = account.key )
        if title :
            album.title = title
        album.put()

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

class DeleteHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        album = utils.get_album_by_key(album_key)
        if album and album.key.parent().get().user_id == users.get_current_user().user_id():
            album.key.delete()
        self.redirect('/')

application = webapp2.WSGIApplication([
    (r'/edit/build', BuildHandler),
    (r'/edit/(.*)', EditHandler),
    (r'/edit/delete/(.*)', DeleteHandler)
    ], debug=True)
