from google.appengine.api import users
from google.appengine.ext import ndb
from models import *
from json import dumps, loads
from google.appengine.api.urlfetch import fetch, POST
import yaml
from google.appengine.ext import blobstore
import base64

def getContext(page):
    """ Gathers necessary information to populate pages

    Returns:
        A dictionary with the info

    """
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
    """ Returns the account object for the current user (also creates one if necessary).

    Args:
        user_id: Google user id
    Returns:
        none if no user logged in, account object otherwise

    """
    #Return none if no user is logged in
    if not user_id:
        user = users.get_current_user()
        if not user:
            return None
        user_id = user.user_id()

    #Get account
    key = ndb.Key('Account', user_id)
    account = key.get()

    #If no account for user exists, make one.
    if not account:
        account = Account(user_id = user_id)
        account.key = key
        account.put()
    return account

def get_albums(user_id):
    """ Gets all a user's albums

    Args:
        user_id: Google user id
    Returns:
        All the albums for that user

    """
    if not user_id:
        user = users.get_current_user()
        if not user:
            return None
        user_id = user.user_id()

    a = Album.query(ancestor = ndb.Key('Account', user_id) ).order(-Album.creation_date)
    return a.fetch()

def get_album_by_key(urlsafe_key):
    """ Converts URL safe key to real key and retrieves associated album

    Args:
        urlsafe_key: URL safe version of an album key
    Returns:
        Album object

    """
    try:
        key = ndb.Key(urlsafe = urlsafe_key)
        return key.get()
    except Exception:
        return None


def vision_api_web_detection(info):
    """ Test for vision api

    Args:
        info: whatever the hell upload is
    Returns:
        First label
        
    """

    data = blobstore.BlobReader(info.key()).read()
    str = base64.b64encode(data)

    with open("config.yaml", 'r') as stream:
        try:
            config = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    payload = {
        "requests": [
            {
                "image": {
                    "content": str
                },
                "features": [
                    {
                        "type": "LABEL_DETECTION",
                    }
                ]
            }
        ]
    }

    response = fetch(
        "https://vision.googleapis.com/v1/images:annotate?key=" + config["API_Key"],
        method=POST,
        payload=dumps(payload),
        headers={"Content-Type": "application/json"}
    )
    result = loads(response.content)
    #main_colors = result[u'responses'][0][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors'][0:3]

    return result[u'responses'][0][u'labelAnnotations'][0][u'description']
