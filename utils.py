from google.appengine.api import users, mail
from google.appengine.ext import ndb
from models import *
from json import dumps, loads
from google.appengine.api import images, urlfetch
from google.appengine.ext import blobstore
from google.appengine.ext.blobstore import BlobKey
import base64
import logging
import yaml
import random

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
        #headers =  {"Content-Type": "image/jpeg", "Content-Length": len(data)}
        headers =  {"Content-Type": "image/jpeg"}
        (status, headers, content) = storage_api.do_request(UPLOAD_BASE_URL_CS + image_name, 'POST', headers, data)
        if status != 200:
          logging.error("Uploading image with filename " + image_name + " failed with status code " + status + " Headers: " + headers)


def generate_dummy_html(account, album_key, image_keys):
  IMG_PER_PAGE = 3 # dummy value for now
  html = ""
  for i in xrange(0, len(image_keys), IMG_PER_PAGE):
    page_imgs = image_keys[i:i+IMG_PER_PAGE]
    img_tags = ""
    (colors, stickers) = get_details_from_cloud_vision(page_imgs)

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

    if stickers:
      random_sticker = random.choice(stickers)
    else:
      random_sticker = ""
    logging.info("Random sticker chosen: " + random_sticker)
    html += """<div class='page'><div class='album_square'>
               <div class='container %s %s' style='background-color: rgb%s'>
                 %s
               </div></div></div>""" % (border, random_sticker, color, img_tags)

  return html



def generate_html(album_key, pages, ratios):
  html = ""
  image_keys = album_key.get().images
  letters = ["a", "b", "c"]
  for page in pages:
    page_imgs = page[1:]

    (palette, stickers) = get_details_from_cloud_vision(page_imgs)

    div_class = page[0]
    if stickers:
        div_class += " sticker %s" % stickers[0]


    img_tags = ""

    for image in page_imgs:
        i = page_imgs.index(image)
        image_url = images.get_serving_url( image, size=300)
        logging.info(image_url)
        img_tags += """<div class='resizer' style='grid-area:%s;'> <img src='%s' style ='background-color: rgb%s'/> </div>""" % (letters[i], image_url, str(tuple(palette[i])))

    style = ""

    r = map(lambda x: ratios[x], page_imgs)
    if page[0] == "3a": #ttw
        columns = "%dfr %dfr" % ( int(100*(1/r[0])/((1/r[0])+(1/r[1])) ), int(100*(1/r[1])/((1/r[0])+(1/r[1]))) )
        rows = "%dfr %dfr" % ( 60, 40 )

        style = """
            grid-template-rows: %s;
            grid-template-columns: %s;
            grid-template-areas: "a b" "c c";
            """ % (rows, columns)

    elif page[0] == "3b": #tww
        rows = "%dfr %dfr" % ( int(100*r[1]/(r[1]+r[2])) , int(100*r[2]/(r[1]+r[2])) )
        columns = "%dfr %dfr" % ( 40, 60 )
        style = """
            grid-template-rows: %s;
            grid-template-columns: %s;
            grid-template-areas: "a b" "a c";
            """ % (rows, columns)
    elif page[0] == "2a": #tt
        columns = "%dfr %dfr" % ( int( 100*(1/r[0] +.5)/((1/r[0])+(1/r[1])+1) ), int(100*(1/r[1] + .5)/((1/r[0])+(1/r[1])+1)) )
        style = """
            grid-template-columns: %s;
            grid-template-areas: "a b";
            """ % (columns)
    elif page[0] == "2b": #ww
        rows = "%dfr %dfr" % ( int(100*(r[0]+.5)/(r[0]+r[1]+1)) , int(100*(r[1]+.5)/(r[0]+r[1]+1)) )
        style = """
            grid-template-rows: %s;
            grid-template-areas: "a" "b";
            """ % (rows)
    else:
        style = """
           display: -webkit-box;
           display: -ms-flexbox;
           display: flex;
           -webkit-box-pack: center;
               -ms-flex-pack: center;
                   justify-content: center;
           -webkit-box-align: center;
               -ms-flex-align: center;
                   align-items: center;
            """
    style += "background-color: rgb%s;" % (str(tuple(palette[3])))

    html += """<div class='page'>
                    <div class='album_square'>
                        <div class='container %s' style='%s'>
                            %s
                        </div>
                    </div>
                </div>""" % (div_class, style, img_tags)

  logging.info("Generated html: " + html)

  return html

def get_details_from_cloud_vision(image_keys):
    urlfetch.set_default_fetch_deadline(600)

    COMMON_LANDMARKS = ["eiffel tower", "statue of liberty", "taj mahal", "golden gate bridge"]
    COMMON_LABELS = ["dog", "cat", "beach", "christmas", "valentine", "heart", "easter", "bunny", "bird"]
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
                                  "maxResults":5
                                  },
                                  {
                                  "type": "LANDMARK_DETECTION",
                                  "maxResults":5
                                  },
                                  {
                                  "type": "LABEL_DETECTION",
                                  "maxResults":5
                                  }
                                ]
                     })
    payload = {
        "requests": requests
    }

    response = urlfetch.fetch(
                     "https://vision.googleapis.com/v1/images:annotate?key=" + config["API_Key"],
                     method=urlfetch.POST,
                     payload=dumps(payload),
                     headers={"Content-Type": "application/json"}
                     )
    results = loads(response.content)
    # logging.info("Result from vision api:")
    # logging.info(results)

    rgb_colors = []
    reds = []
    greens = []
    blues = []
    stickers = []

    for i in xrange(0, len(image_keys)):
      colors = results[u'responses'][i][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors']
      #main_color = sorted(colors, key = lambda color : color[u'pixelFraction'] + color[u'score'] , reverse = True)[0]
      if len(image_keys) < 3:
        num_colors = 2 if len(image_keys) == 2 else 3
        main_colors = sorted(colors, key = lambda color : 0 * color[u'pixelFraction'] + color[u'score'] , reverse = True)[0:num_colors]
        for main_color in main_colors:
          info = main_color[u'color']
          rgb = [info[u'red'], info[u'green'], info[u'blue']]
          reds.append(rgb[0])
          greens.append(rgb[1])
          blues.append(rgb[2])
          rgb_colors.append(rgb)
      else:
        main_color = sorted(colors, key = lambda color : 0 * color[u'pixelFraction'] + color[u'score'] , reverse = True)[0]
        info = main_color[u'color']
        rgb = [info[u'red'], info[u'green'], info[u'blue']]
        reds.append(rgb[0])
        greens.append(rgb[1])
        blues.append(rgb[2])

        rgb_colors.append(rgb)

      logging.info("Length of stickers so far: " + str(len(stickers)))

      labels = results[u'responses'][0][u'labelAnnotations']
      labels = sorted(labels, key = lambda annotation : annotation[u'score'] , reverse = True)[0:5]
      for label in labels:
        label = label[u'description']
        if label in COMMON_LABELS:
          stickers.append(label)

      try:
        landmark = results[u'responses'][i][u'landmarkAnnotations']
        landmark = sorted(landmark, key = lambda annotation : annotation[u'score'] , reverse = True)[0]
        landmark_name = landmark[u'description']
        if landmark_name.lower() in COMMON_LANDMARKS:
          stickers.append(landmark_name)
      except KeyError:
        pass

    logging.info("Stickers: " + str(stickers))

    average_rgb = [ sum(reds)/len(reds), sum(greens)/len(greens), sum(blues)/len(blues)]
    rgb_colors.append(average_rgb)

    logging.info("Sending " + str(len(rgb_colors)) + " colors to colormind")

    palette_response = urlfetch.fetch(
                         'http://colormind.io/api/',
                         method=urlfetch.POST,
                         payload= '{"input": %s , "model":"default" }' % (str(rgb_colors)),
                         headers={"Content-Type": "application/json"}
                         )
    palette = loads(palette_response.content)[u'result']

    # color at index 4 will be the background color of the page. This check here is to
    # catch the case where a grayscale image gets a super bright background
    is_grayscale = []
    for i in xrange(0, len(reds)):
      if abs(reds[i] - greens[i]) <= 25 and abs(reds[i] - blues[i]) <= 25 and abs(greens[i] - blues[i]) <= 25:
        logging.info("Determined that color with rgb %d, %d, %d is grayscale" % (reds[i], greens[i], blues[i]))
        is_grayscale.append(True)
      else:
        logging.info("Determined that color with rgb %d, %d, %d is NOT grayscale" % (reds[i], greens[i], blues[i]))
        is_grayscale.append(False)

    [red, green, blue] = palette[3]
    if not (abs(red - green) <= 25 and abs(red - blue) <= 25 and abs(green - blue) <= 25):
      logging.info("Determined that the background color (%d, %d, %d) was too vibrant, resorting to average (%d, %d, %d)" % (palette[3][0], palette[3][1], palette[3][2], average_rgb[0], average_rgb[1], average_rgb[2]))
      palette[3] = average_rgb

    return (palette, stickers)

def send_album_email(name, email, album_key):
    logging.info("sending mail!")
    album = get_album_by_key(album_key)
    title = album.title
    url = "lazycloudalbum.appspot.com/create/%s" % (album_key)
    mail.send_mail(
        sender="noreply@lazycloudalbum.appspotmail.com",
        subject= "%s has been built!" %(title),
        to = email,
        body = """
        Hey %s,

        We've finished putting together your '%s' album.
        <a href = '%s'> Check it out! </a>
        """ % (name, title, )
         )
