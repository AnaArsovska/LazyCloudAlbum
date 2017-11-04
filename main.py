import jinja2
import os
import webapp2
import utils

from google.appengine.api import users

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir))

class MainPage(webapp2.RequestHandler):
    def get(self):
        context = utils.getContext(self)
        if not context['user']:
            template = template_env.get_template('welcome.html.j2')
        else:
            context['albums'] = utils.get_albums( context['user'].user_id() )
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
        self.response.out.write(template.render(context))

class ViewPage(webapp2.RequestHandler):
    def get(self, album_key):
        context = utils.getContext(self)
        album = utils.get_album_by_key(album_key)
        if album:
            if album.public or album.key.parent().get().user_id == context['user'].user_id() :
                context['album'] = album
                context["delete"] = "/edit/delete/" + album_key
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
