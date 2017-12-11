import webapp2
import models
import utils
import logging

from google.appengine.ext import ndb, blobstore
from google.appengine.api import app_identity, users, images
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api.taskqueue import taskqueue

class BuildHandler(blobstore_handlers.BlobstoreUploadHandler):
    @ndb.transactional
    def post(self):
        """ Build Handler puts album in the datastore then adds album to task queue to be generated.
        """
        logging.info("html from request: " + str(self.request.get('html')).strip())
        title = str(self.request.get('title')).strip()
        account = utils.get_account()
        album = models.Album( parent = account.key )
        album.public = album.public = True if self.request.get('public') else False #bool() not working
        if self.get_uploads():
            uploads = [x for x in self.get_uploads() if x.size < 4000000]

        if title :
            album.title = title

        if uploads:
            thumbnail_blob_key = uploads[0].key()
            for upload in uploads:
                album.images.append(str(upload.key()))
            utils.upload_album_images_to_cloud_storage(account, album, uploads)
        else:
            thumbnail_blob_key = None

        if thumbnail_blob_key:
            thumbnail_url = images.get_serving_url(thumbnail_blob_key, size=200, crop=True)
            album.thumbnail_url = thumbnail_url
        else:
            album.thumbnail_url = ""

        album.put()

        user = users.get_current_user()

        task = taskqueue.add(
           url='/construction',
           params={'album': album.key.urlsafe(),
                    'email':user.email(),
                    'name': user.nickname() },
           target = 'worker',
           retry_options=taskqueue.TaskRetryOptions(task_retry_limit=3),
           transactional = True)

        #redirect moved to javascript, browser doesn't honor ajax redirects

class DeleteHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        """ Deletes album specified by URL

        Args:
            album_key: URL safe version of the album key

        """
        album = utils.get_album_by_key(album_key)
        if album and album.key.parent().get().user_id == users.get_current_user().user_id():
            album.hidden = True
            album.put()
            task = taskqueue.add(
               url='/delete',
               params={'album': album_key},
               target = 'worker',
               transactional = True)
        #redirect moved to view.html.j2

class EditHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        """Edits properties of album specified by URL

        Args:
            album_key: URL safe version of the album key

        """
        album = utils.get_album_by_key(album_key)
        title = str(self.request.get('title')).strip()
        if title :
            album.title = title
        album.public = True if self.request.get('public') else False #bool() not working
        logging.info(self.request.get('public'))
        album.put()
        self.redirect('/')

class AlbumReadyHandler(webapp2.RequestHandler):
    def post(self, album_key):
        """Checks if a given album is ready. Sends response 200 if it is, and 204 if not.

        Args:
            album_key: URL safe version of the album key

        """
        album = utils.get_album_by_key(album_key)
        if album.ready:
            logging.info("Album with id %s is ready!" % (album_key))
            self.response.set_status(200)
        else:
            logging.info("Album with id %s is not ready yet" % (album_key))
            self.response.set_status(204)

application = webapp2.WSGIApplication([
    (r'/edit/build', BuildHandler),
    (r'/edit/delete/(.*)', DeleteHandler),
    (r'/edit/ready/(.*)', AlbumReadyHandler),
    (r'/edit/(.*)', EditHandler)
    ], debug=True)
