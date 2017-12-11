import jinja2
import os
import webapp2
import utils
import logging

from google.appengine.api import users
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.blobstore import BlobKey

#Makes templates file accessible
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
template_env = jinja2.Environment( loader=jinja2.FileSystemLoader(template_dir) )

class MainPage(webapp2.RequestHandler):
    def get(self):
        """ Loads main page """
        context = utils.getContext(self)
        # If no user is logged in, load generic welcome page
        if not context['user']:
            template = template_env.get_template('welcome.html.j2')
        else:
            context['albums'] = utils.get_albums( context['user'].user_id())
            # If they have no albums, load instructions page
            if not context['albums'] :
                template = template_env.get_template('tutorial.html.j2')
            # Otherwise, load their albums
            else:
                template = template_env.get_template('albums.html.j2')
        self.response.out.write(template.render(context))


class AboutPage(webapp2.RequestHandler):
    def get(self):
        """ Loads about page """
        context = utils.getContext(self)
        template = template_env.get_template('about.html.j2')
        self.response.out.write(template.render(context))

class HowToPage(webapp2.RequestHandler):
    def get(self):
        """ Loads instruction page """
        context = utils.getContext(self)
        template = template_env.get_template('how_to.html.j2')
        self.response.out.write(template.render(context))

class ContactPage(webapp2.RequestHandler):
    def get(self):
        """ Loads contact page """
        template = template_env.get_template('contact.html.j2')
        self.response.out.write(template.render())

class CreatePage(webapp2.RequestHandler):
    def get(self):
        """ Loads album creation page """
        context = utils.getContext(self)
        template = template_env.get_template('create.html.j2')
        upload_url = blobstore.create_upload_url('/edit/build')
        logging.info("upload url: %s", upload_url)
        self.response.out.write(template.render(context, upload_url=upload_url))

class ErrorPage(webapp2.RequestHandler):
    def get(self):
        """ Loads error page """
        context = utils.getContext(self)
        template = template_env.get_template('album_create_error.html.j2')
        self.response.out.write(template.render(context))

class ViewPage(webapp2.RequestHandler):
    def get(self, album_key):
        """ Views album specified by URL

            Args:
            album_key: URL safe version of the album key

            """
        context = utils.getContext(self)
        album = utils.get_album_by_key(album_key)
        if album:
            # Show album only if it is public or the current user is the owner
            if album.public or (context['user'] and album.key.parent().get().user_id == context['user'].user_id()) :
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
                #Private album
                template = template_env.get_template('private.html.j2')
        else:
            #Album with that key does not exist
            template = template_env.get_template('nothing_here.html.j2')
        self.response.out.write(template.render(context))


class test(webapp2.RequestHandler):
    def get(self):
        """ Loads test page """
        template = template_env.get_template('test.html.j2')
        self.response.out.write(template.render())

application = webapp2.WSGIApplication([
                                       (r'/about', AboutPage),
                                       (r'/how_to', HowToPage),
                                       (r'/create', CreatePage),
                                       (r'/error', ErrorPage),
                                       (r'/view/(.*)', ViewPage),
                                       (r'/contact', ContactPage),
                                       (r'/', MainPage)], debug=True)
