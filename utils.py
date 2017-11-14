from google.appengine.api import users
from google.appengine.ext import ndb
from models import *
from json import dumps, loads
from google.appengine.api.urlfetch import fetch, POST
import yaml

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


def vision_api_web_detection(uri):
    """This is the minimal code to accomplish a web detect request to the google vision api
    You don't need 56 MiB of python client code installing 'google-cloud-vision' to accomplish
    that task on google app engine, which does not even work.
    .. TODO:: you should have secured your api key before you deploy this code snippet.
    Please take a look at https://support.google.com/cloud/answer/6310037?hl=en
    :param uri: the complete uri to compare against the web
    :type uri: str
    :return: the result dictionary
    :rtype: dict
    """

    with open("config.yaml", 'r') as stream:
        try:
            config = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    payload = {
        "requests": [
            {
                "image": {
                    "source": {
                        "imageUri": uri
                    }
                },
                "features": [
                    {
                        "type": "IMAGE_PROPERTIES"
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
    return str(result)[0:1000]
