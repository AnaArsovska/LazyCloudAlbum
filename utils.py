from google.appengine.api import users
from google.appengine.ext import ndb
from models import *
from json import dumps, loads
from google.appengine.api.urlfetch import fetch, POST
import yaml
from google.appengine.ext import blobstore
import base64
import logging

from google.appengine.ext import vendor
vendor.add('lib')
import cloudstorage

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

def get_html_filename(account, album_key):
    return account.user_id + "/" + str(album_key) + "/html"

def get_photo_filename(account, album_key, photo):
    return get_photo_filename_by_key(account, album_key, photo.key())

def get_photo_filename_by_key(account, album_key, photo_key):
    return account.user_id + "/" + str(album_key) + "/photos/" + str(photo_key)

def clear_album_data(album):
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    for image_key in album.images:
        blobstore.delete(image_key)
        
        cloudstorage_filename = get_photo_filename_by_key(album.key.parent().get(), album.key.urlsafe(), image_key)
        cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
        
        storage_api.do_request("https://www.googleapis.com/storage/v1/b/lazy_cloud_album_test/o/" + cloudstorage_filename,
                               'DELETE')
            
            cloudstorage_filename = get_html_filename(album.key.parent().get(), album.key.urlsafe())
            cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
            storage_api.do_request("https://www.googleapis.com/storage/v1/b/lazy_cloud_album_test/o/" + cloudstorage_filename,
                                   'DELETE')

def get_html_from_cloud_storage(account, album_key):
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    file_name = get_html_filename(account, album_key)
    
    file_name = file_name.replace("/", "%2f")
    (status, headers, content) = storage_api.do_request("https://www.googleapis.com/storage/v1/b/lazy_cloud_album_test/o/" + file_name + "?alt=media",'GET')
        
        # Returns (success, response)
        if status == 200:
            return (True, content)
                else:
                    return (False, "Error: No HTML found for the given user")

def upload_file_to_cloud_storage(account, info, album_key):
    data = blobstore.BlobReader(info.key()).read()
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    
    image_name = get_photo_filename(account, album_key, info)
    headers =  {"Content-Type": "image/jpeg", "Content-Length": len(data)}
    storage_api.do_request("https://www.googleapis.com/upload/storage/v1/b/lazy_cloud_album_test/o?uploadType=media&name=" + image_name,'POST', headers, data)
    
    my_message = "Hello there world! I am the saved HTML for user " + account.user_id + " for album " str(album_key)
    
    headers =  {"Content-Type": "text/plain"}
        html_content_name = get_html_filename(account, album_key)
        logging.info("Saving html with filename:" + html_content_name)
        storage_api.do_request("https://www.googleapis.com/upload/storage/v1/b/lazy_cloud_album_test/o?uploadType=media&name=" + html_content_name,
                               'POST', headers, my_message)

def vision_api_web_detection(info):
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
    
    data = blobstore.BlobReader(info.key()).read()
    image_str = base64.b64encode(data)
    # im = Image.open(BytesIO(data))
    # quantize_js(im)
    
    with open("config.yaml", 'r') as stream:
        try:
            config = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

payload = {
    "requests": [
                 {
                 "image": {
                 "content": image_str
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
                
                # Returns (success, response). Response is empty if an error occurred
                try:
                    label = result[u'responses'][0][u'labelAnnotations'][0][u'description']
                    return (True, label)
                        except KeyError:
                            return (False, "")




def vision_api_web_detection2(info):
    """ Test for vision api
        
        Args:
        info: whatever the hell upload is
        Returns:
        First label
        
        """
    
    data = blobstore.BlobReader(info.key()).read()
    string = base64.b64encode(data)
    
    with open("config.yaml", 'r') as stream:
        config = yaml.load(stream)
            
            payload = {
                "requests": [
                             {
                             "image": {
                             "content": string
                             },
                             "features": [
                                          {
                                          "type": "IMAGE_PROPERTIES",
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
        colors = result[u'responses'][0][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors']
        main_colors = sorted(colors, key = lambda color : color[u'pixelFraction'] + color[u'score'] , reverse = True)[0:5]
        rgb_colors = []
        for color in main_colors:
            info = color[u'color']
            rgb = [info[u'red'], info[u'green'], info[u'blue'],]
            rgb_colors.append(rgb)

palette_response = fetch(
                         'http://colormind.io/api/',
                         method=POST,
                         payload= '{"input": %s , "model":"default" }' % (str(rgb_colors)),
                         headers={"Content-Type": "application/json"}
                         )
    palette = loads(palette_response.content)[u'result']
    
    return str(palette) #result[u'responses'][0][u'imagePropertiesAnnotation'][0][u'description']

