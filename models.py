from google.appengine.api import users
from google.appengine.ext import ndb

class Account(ndb.Model):
    user_id = ndb.StringProperty(required=True)

@ndb.transactional
def get_account(user_id=None):
    if not user_id:
        user = users.get_current_user()
        if not user:
            return None
        user_id = user.user_id()

    key = ndb.Key('Account', user_id)
    account = key.get()
    if not account:
        account = Account(user_id = user_id)
        account.key = key
        account.put()
    return account

class Album(ndb.Model):
    title = ndb.StringProperty(default="Untitled Album")
    creation_date = ndb.DateTimeProperty(auto_now_add=True)
    html = ndb.StringProperty(default = "Cats")
    public = ndb.BooleanProperty(default = True)

def get_albums(user_id):
    if not user_id:
        user = users.get_current_user()
        if not user:
            return None
        user_id = user.user_id()

    a = Album.query(ancestor = ndb.Key('Account', user_id) ).order(-Album.creation_date)
    return a.fetch()

def get_album_by_key(urlsafe_key):
    try:
        key = ndb.Key(urlsafe = urlsafe_key)
        return key.get()
    except Exception:
        return None
