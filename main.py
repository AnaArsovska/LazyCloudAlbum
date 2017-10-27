import jinja2
import os
import webapp2
import models

from google.appengine.api import users

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir))

class MainPage(webapp2.RequestHandler):
    def get(self):
        context = getContext(self)
        if not context['user']:
            template = template_env.get_template('welcome.html.j2')
        else:
            context['albums'] = models.get_albums( context['user'].user_id() )
            if not context['albums'] :
                template = template_env.get_template('tutorial.html.j2')
            else:
                template = template_env.get_template('albums.html.j2')
        self.response.out.write(template.render(context))


class AboutPage(webapp2.RequestHandler):
    def get(self):
        context = getContext(self)
        template = template_env.get_template('about.html.j2')
        self.response.out.write(template.render(context))

class HowToPage(webapp2.RequestHandler):
    def get(self):
        context = getContext(self)
        template = template_env.get_template('how_to.html.j2')
        self.response.out.write(template.render(context))

class CreatePage(webapp2.RequestHandler):
    def get(self):
        context = getContext(self)
        template = template_env.get_template('create.html.j2')
        self.response.out.write(template.render(context))

class ViewPage(webapp2.RequestHandler):
    def get(self, album_key):
        context = getContext(self)
        album = models.get_album_by_key(album_key)
        if album:
            if album.public:
                context['album'] = album
                template = template_env.get_template('view.html.j2')
            else:
                template = template_env.get_template('private.html.j2')
        else:
            template = template_env.get_template('nothing_here.html.j2')
        self.response.out.write(template.render(context))

def getContext(page):
    user = users.get_current_user()
    login_url = users.create_login_url(page.request.path)
    logout_url = users.create_logout_url(page.request.path)
    if user:
        account = models.get_account( user.user_id() )
    else:
        account = None
    context = {
        'login_url': login_url,
        'user': user,
        'logout_url': logout_url,
        'account': account
    }
    return context

application = webapp2.WSGIApplication([
    (r'/about', AboutPage),
    (r'/how_to', HowToPage),
    (r'/create', CreatePage),
    (r'/view/(.*)', ViewPage),
    (r'/', MainPage)], debug=True)
