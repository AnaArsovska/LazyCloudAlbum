import webapp2
import models
import utils
import os
import logging
import jinja2

from google.appengine.ext import ndb, blobstore
from google.appengine.api import app_identity, users, images
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api.taskqueue import taskqueue


template_dir = os.path.join(os.path.dirname(__file__), 'templates')

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir))

class BuildHandler(blobstore_handlers.BlobstoreUploadHandler):
    @ndb.transactional
    def post(self):
        """ Build Handler constructs album based on uploaded pictures """
        logging.info("html from request: " + str(self.request.get('html')).strip())
        title = str(self.request.get('title')).strip()
        account = utils.get_account()
        album = models.Album( parent = account.key )
        album.public = album.public = True if self.request.get('public') else False #bool() not working
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

            # this is throwing mad RequestTooLargeErrors -> (success, html) = utils.vision_api_web_detection(self.get_uploads()[0])
            #if success:
            #    album.html = html
            #else:
            #    self.redirect('/edit/error')
            #    return
        else:
            album.thumbnail_url = ""

        album.put()

        utils.upload_album_images_to_cloud_storage(account, album, self.get_uploads())

        html = utils.generate_dummy_html(album.images)
        filename = utils.get_html_filename(account, album.key.urlsafe())
        utils.upload_text_file_to_cloudstorage(filename, html)

        task = taskqueue.add(
           url='/construction',
           params={'album': album.key.urlsafe()},
           target = 'worker',
           transactional = True)

        logging.info("I should redirect")
        #redirect moved to javascript, browser doesn't honor ajax redirects

class ErrorPage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        template = template_env.get_template('album_create_error.html.j2')
        self.response.out.write(template.render(context))

class DeleteHandler(webapp2.RequestHandler):
    @ndb.transactional
    def post(self, album_key):
        """ Deletes album specified by URL

        Args:
            album_key: URL safe version of the album key

        """
        album = utils.get_album_by_key(album_key)
        if album and album.key.parent().get().user_id == users.get_current_user().user_id():
            utils.clear_album_data(album)
            album.key.delete()
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
        album.public = bool(self.request.get("public"))
        album.put()
        self.redirect('/')

application = webapp2.WSGIApplication([
    (r'/edit/build', BuildHandler),
    (r'/edit/error', ErrorPage),
    (r'/edit/delete/(.*)', DeleteHandler),
    (r'/edit/(.*)', EditHandler)
    ], debug=True)
