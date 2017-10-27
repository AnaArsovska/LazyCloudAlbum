import webapp2
import models

from google.appengine.ext import ndb

class BuildPage(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self):
        title = str(self.request.get('title'))
        account = models.get_account()
        album = models.Album( parent = account.key)
        if title :
            album.title = title
        album.put()
        self.redirect('/')

application = webapp2.WSGIApplication([('/build', BuildPage)], debug=True)
