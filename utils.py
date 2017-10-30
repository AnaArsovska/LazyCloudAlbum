from google.appengine.api import users
from google.appengine.ext import ndb
from models import *

def getContext(page):
    user = users.get_current_user()
    login_url = users.create_login_url(page.request.path)
    logout_url = users.create_logout_url(page.request.path)
    if user:
        account = get_account( user.user_id() )
    else:
        account = None
    context = {
        'login_url': login_url,
        'user': user,
        'logout_url': logout_url,
        'account': account
    }
    return context

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
