import jinja2
import os
import webapp2
import utils
import logging

from google.appengine.api import users
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.blobstore import BlobKey

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir))

class MainPage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        if not context['user']:
            template = template_env.get_template('welcome.html.j2')
        else:
            context['albums'] = utils.get_albums( context['user'].user_id())
            if not context['albums'] :
                template = template_env.get_template('tutorial.html.j2')
            else:
                template = template_env.get_template('albums.html.j2')
        self.response.out.write(template.render(context))


class AboutPage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        template = template_env.get_template('about.html.j2')
        self.response.out.write(template.render(context))

class HowToPage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        template = template_env.get_template('how_to.html.j2')
        self.response.out.write(template.render(context))

class CreatePage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        template = template_env.get_template('create.html.j2')
        upload_url = blobstore.create_upload_url('/edit/build')
        logging.info("upload url: %s", upload_url)
        self.response.out.write(template.render(context, upload_url=upload_url))

class ViewPage(webapp2.RequestHandler):
    def get(self, album_key):
        context = utils.getContext(self)
        album = utils.get_album_by_key(album_key)
        if album:
            if album.public or album.key.parent().get().user_id == context['user'].user_id() :
                context['album'] = album
                context["delete"] = "/edit/delete/" + album_key
                image_urls = []
                if album.images:
                    for image_key in album.images:
                        image_urls.append(images.get_serving_url(BlobKey(image_key), size=300))
                context['images'] = image_urls
                # get_html_from_cloud_storage returns the tuple (success, content). We ignore the first value and just take
                # the content since it returns an error message for "content" if it did not succeed
                (_, context['saved_html']) = utils.get_html_from_cloud_storage(album.key.parent().get(), album.key.urlsafe())
                template = template_env.get_template('view.html.j2')
            else:
                template = template_env.get_template('private.html.j2')
        else:
            template = template_env.get_template('nothing_here.html.j2')
        self.response.out.write(template.render(context))

application = webapp2.WSGIApplication([
    (r'/about', AboutPage),
    (r'/how_to', HowToPage),
    (r'/create', CreatePage),
    (r'/view/(.*)', ViewPage),
    (r'/', MainPage)], debug=True)
