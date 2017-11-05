from google.appengine.api import users
from google.appengine.ext import ndb

class Account(ndb.Model):
    user_id = ndb.StringProperty(required=True)

class Album(ndb.Model):
    title = ndb.StringProperty(default="Untitled Album")
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    html = ndb.StringProperty(default = "Cats")
    thumbnail_url = ndb.StringProperty(default="")
    public = ndb.BooleanProperty(default = True)
