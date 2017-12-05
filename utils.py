from google.appengine.api import users, mail
from google.appengine.ext import ndb
from models import *
from json import dumps, loads
from google.appengine.api.urlfetch import fetch, POST
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.blobstore import BlobKey
import base64
import logging
import yaml

from google.appengine.ext import vendor
vendor.add('lib')
import cloudstorage

BUCKET_NAME = "lazy_cloud_album_test"
UPLOAD_BASE_URL_CS = "https://www.googleapis.com/upload/storage/v1/b/" + BUCKET_NAME + "/o?uploadType=media&name="
DELETE_BASE_URL_CS = "https://www.googleapis.com/storage/v1/b/lazy_cloud_album_test/o/"
GET_BASE_URL_CS = "https://www.googleapis.com/storage/v1/b/lazy_cloud_album_test/o/"

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

    a = Album.query(Album.hidden == False, ancestor = ndb.Key('Account', user_id) ).order(-Album.creation_date)
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

        storage_api.do_request(DELETE_BASE_URL_CS + cloudstorage_filename,
                               'DELETE')

        cloudstorage_filename = get_html_filename(album.key.parent().get(), album.key.urlsafe())
        cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
        storage_api.do_request(DELETE_BASE_URL_CS + cloudstorage_filename,
                               'DELETE')

def get_html_from_cloud_storage(account, album_key):
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    file_name = get_html_filename(account, album_key)
    file_name = file_name.replace("/", "%2f")
    (status, headers, content) = storage_api.do_request(GET_BASE_URL_CS + file_name + "?alt=media",'GET')

    # Returns (success, response)
    if status == 200:
        return (True, content)
    else:
        return (False, "Error: No HTML found for the given user")

def upload_text_file_to_cloudstorage(filename, contents):
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    headers =  {"Content-Type": "text/plain"}
    logging.info("Saving text file with filename:" + filename)
    (status, headers, content) = storage_api.do_request(UPLOAD_BASE_URL_CS + filename, 'POST', headers, contents)
    if status == 200:
      logging.info("Uploading html with filename " + filename + " succeeded")
    else:
      logging.error("Uploading html with filename " + filename + " failed with status code " + status + ". Headers: " + headers)



def upload_album_images_to_cloud_storage(account, album, images):
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    for image in images:
        data = blobstore.BlobReader(image.key()).read()

        image_name = get_photo_filename(account, album.key.urlsafe(), image)
        headers =  {"Content-Type": "image/jpeg", "Content-Length": len(data)}
        (status, headers, content) = storage_api.do_request(UPLOAD_BASE_URL_CS + image_name, 'POST', headers, data)
        if status != 200:
          logging.error("Uploading image with filename " + image_name + " failed with status code " + status + " Headers: " + headers)


def generate_dummy_html(account, album_key, image_keys):
  IMG_PER_PAGE = 3 # dummy value for now
  html = ""
  for i in xrange(0, len(image_keys), IMG_PER_PAGE):
    page_imgs = image_keys[i:i+IMG_PER_PAGE]
    img_tags = ""
    colors = get_dominant_colors(page_imgs)

    i = 0
    for image in page_imgs:
      image_url = images.get_serving_url(BlobKey(image), size=300)
      image_filename = get_photo_filename_by_key(account, album_key, image)
      color = str( (colors[i][0], colors [i][1], colors[i][2]))
      logging.info("Got color for image: " + color)
      img_tags += """<img src='%s' style='background-color: rgb%s'/>""" % (image_url, color)
      i += 1

    rgb_sum = sum(colors[3])
    if rgb_sum > (128 * 3):
      border = "black"
    else:
      border = "white"
    color = str( (colors[3][0], colors [3][1], colors[3][2]))

    # class container black or container white
    html += """<div class='page'><div class='album_square'><div class='container %s' style='background-color: rgb%s'>%s</div></div></div>""" % (border, color, img_tags)

  logging.info("Generated html: " + html)
  return html

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

def get_dominant_colors(image_keys):


    with open("config.yaml", 'r') as stream:
        config = yaml.load(stream)

    requests = []
    for image_key in image_keys:
      data = blobstore.BlobReader(image_key).read()
      string = base64.b64encode(data)
      requests.append({
                     "image": {
                      "content": string

                     },
                     "features": [
                                  {
                                  "type": "IMAGE_PROPERTIES",
                                  }
                                ]
                     })
    payload = {
        "requests": requests
    }

    response = fetch(
                     "https://vision.googleapis.com/v1/images:annotate?key=" + config["API_Key"],
                     method=POST,
                     payload=dumps(payload),
                     headers={"Content-Type": "application/json"}
                     )
    results = loads(response.content)
    logging.info("Result from vision api:")
    logging.info(results)

    rgb_colors = []
    reds = []
    greens = []
    blues = []
    for i in xrange(0, len(image_keys)):
      colors = results[u'responses'][i][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors']
      #main_color = sorted(colors, key = lambda color : color[u'pixelFraction'] + color[u'score'] , reverse = True)[0]
      main_color = sorted(colors, key = lambda color : 0 * color[u'pixelFraction'] + color[u'score'] , reverse = True)[0]
      info = main_color[u'color']
      rgb = [info[u'red'], info[u'green'], info[u'blue']]
      reds.append(rgb[0])
      greens.append(rgb[1])
      blues.append(rgb[2])

      rgb_colors.append(rgb)

    average_rgb = [ sum(reds)/len(reds), sum(greens)/len(greens), sum(blues)/len(blues)]
    rgb_colors.append(average_rgb)

    palette_response = fetch(
                         'http://colormind.io/api/',
                         method=POST,
                         payload= '{"input": %s , "model":"default" }' % (str(rgb_colors)),
                         headers={"Content-Type": "application/json"}
                         )
    palette = loads(palette_response.content)[u'result']
    return palette


def vision_api_web_detection_colors(info):
    """ Test for vision api

        Args:
        info: whatever the hell upload is
        Returns:
        First label

        """

    data = blobstore.BlobReader(info).read()
    string = base64.b64encode(data)

    with open("config.yaml", 'r') as stream:
        config = yaml.load(stream)

    #file_name = file_name.replace("/", "%2f")
    #logging.info("Uri: " + ("gs://%s/%s" % (BUCKET_NAME, file_name)))
    payload = {
        "requests": [
                     {
                     "image": {
                      "content": string
                      #"source": { "imageUri": "gs://%s/%s" % (BUCKET_NAME, file_name) }
                     },
                     "features": [
                                  {
                                  "type": "IMAGE_PROPERTIES",
                                  }
                                ]
                     },
                     {
                     "image": {
                      "content": string
                      #"source": { "imageUri": "gs://%s/%s" % (BUCKET_NAME, file_name) }
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
    logging.info("Result from vision api:")
    logging.info(result)
    # colors = result[u'responses'][0][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors']
    # main_colors = sorted(colors, key = lambda color : color[u'pixelFraction'] + color[u'score'] , reverse = True)[0:5]
    # rgb_colors = []
    # for color in main_colors:
    #     info = color[u'color']
    #     rgb = [info[u'red'], info[u'green'], info[u'blue']]
    #     rgb_colors.append(rgb)

    # palette_response = fetch(
    #                      'http://colormind.io/api/',
    #                      method=POST,
    #                      payload= '{"input": %s , "model":"default" }' % (str(rgb_colors)),
    #                      headers={"Content-Type": "application/json"}
    #                      )
    # palette = loads(palette_response.content)[u'result']

    # logging.info("Got the palette: " + str(palette))

    #return palette #result[u'responses'][0][u'imagePropertiesAnnotation'][0][u'description']
    return (0,0,0)

def send_album_email(name, email, album_key):
    logging.info("sending mail!")
    album = get_album_by_key(album_key)
    mail.send_mail(
        sender="noreply@lazycloudalbum.appspotmail.com",
        subject= "%s has been built!" %(title),
        to = email,
        #email template found at https://github.com/leemunroe/responsive-html-email-template
        body = """
        """
         )
