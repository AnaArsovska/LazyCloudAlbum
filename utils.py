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
import ast

from google.appengine.ext import vendor
vendor.add('lib')
import cloudstorage

with open("config.yaml", 'r') as stream:
  config = yaml.load(stream)
  BUCKET_NAME = config["BUCKET_NAME"]

UPLOAD_BASE_URL_CS = "https://www.googleapis.com/upload/storage/v1/b/" + BUCKET_NAME + "/o?uploadType=media&name="
DELETE_BASE_URL_CS = "https://www.googleapis.com/storage/v1/b/" + BUCKET_NAME + "/o/"
GET_BASE_URL_CS = "https://www.googleapis.com/storage/v1/b/" + BUCKET_NAME + "/o/"

# Used to disable calls to vision api when testing non-vision related features
# SET TO FALSE BEFORE DEPLOYING
MINIMIZE_BILLING = False

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

def get_vision_cache_filename(account, album_key, photo_key):
    photos_filename = get_photo_filename_by_key(account, album_key, photo_key)
    return photos_filename.replace("photos", "vision_results")

def get_photo_filename_by_key(account, album_key, photo_key):
    return account.user_id + "/" + str(album_key) + "/photos/" + str(photo_key)

def clear_album_data(album):
    """ Deletes all files from cloud storage and the blobstore for a given
        album.

        Args:
          album: an Album entity
        """
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    for image_key in album.images:
        blobstore.delete(image_key)

        cloudstorage_filename = get_photo_filename_by_key(album.key.parent().get(), album.key.urlsafe(), image_key)
        cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
        storage_api.do_request(DELETE_BASE_URL_CS + cloudstorage_filename,
                               'DELETE')

        cloudstorage_filename = get_vision_cache_filename(album.key.parent().get(), album.key.urlsafe(), image_key)
        cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
        storage_api.do_request(DELETE_BASE_URL_CS + cloudstorage_filename,
                               'DELETE')

    cloudstorage_filename = get_html_filename(album.key.parent().get(), album.key.urlsafe())
    cloudstorage_filename = cloudstorage_filename.replace("/","%2f")
    storage_api.do_request(DELETE_BASE_URL_CS + cloudstorage_filename,
                           'DELETE')

def get_html_from_cloud_storage(account, album_key):
    """ Reads the html file for a given account and album from Cloud Storage.

        Args:
          account: an Account entity
          album_key: urlsafe version of the entity key for the Album

        Returns:
        The tuple (success, content) where success is a bool representing whether the file was found
        and content is the contents of the html file

        """
    # storage_api = cloudstorage.storage_api._get_storage_api(None)
    file_name = get_html_filename(account, album_key)
    # file_name = file_name.replace("/", "%2f")
    # (status, headers, content) = storage_api.do_request(GET_BASE_URL_CS + file_name + "?alt=media",'GET')

    # if status == 200:
    #     return (True, content)
    # else:
    #     return (False, "Error: No HTML found for the given user")
    (success, content) = get_file_from_cloud_storage(file_name)
    if not success:
      content = "Error: No HTML found for the given user"

    return (success, content)

def get_file_from_cloud_storage(file_name):
    """ Reads a file with the given filename from Cloud Storage.

        Args:
          file_name: The path to the file on cloud storage. Does not need to be URI safe

        Returns:
        The tuple (success, content) where success is a bool representing whether the file was found
        and content is the contents of the file

        """
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    file_name = file_name.replace("/", "%2f")
    (status, headers, content) = storage_api.do_request(GET_BASE_URL_CS + file_name + "?alt=media",'GET')

    if status == 200:
        return (True, content)
    else:
        return (False, None)

def upload_text_file_to_cloudstorage(filename, contents):
    """ Uploads a text file with the given name and contents to Cloud Storage.

        Args:
          filename: a string representing the name of the file (does not need to be URI safe)
          contents: a string representing the contents of the file

        Logs an error if uploading failed.

        """
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    headers =  {"Content-Type": "text/plain"}
    logging.info("Saving text file with filename:" + filename)
    (status, headers, content) = storage_api.do_request(UPLOAD_BASE_URL_CS + filename, 'POST', headers, contents)
    if status == 200:
      logging.info("Uploading html with filename " + filename + " succeeded")
    else:
      logging.error("Uploading html with filename " + filename + " failed with status code " + str(status) + ". Headers: " + str(headers))



def upload_album_images_to_cloud_storage(account, album, images):
    """ Uploads a set of images to google cloud storage.

        Args:
          account: an Account entity
          album: an Album entity
          images: a list of image data (from web form)

        Logs an error if uploading failed.

        """
    storage_api = cloudstorage.storage_api._get_storage_api(None)
    for image in images:
        data = blobstore.BlobReader(image.key()).read()

        image_name = get_photo_filename(account, album.key.urlsafe(), image)
        headers =  {"Content-Type": "image/jpeg"}
        (status, headers, content) = storage_api.do_request(UPLOAD_BASE_URL_CS + image_name, 'POST', headers, data)
        if status != 200:
          logging.error("Uploading image with filename " + image_name + " failed with status code " + str(status) + " Headers: " + str(headers))

def generate_html(album_key, pages, ratios):
  """ Generates the HTML for the album with the given key and images.

    Args:
    album_key: an Album entity key (NOT urlsafe)
    pages: an list of pages of the form page type (eg: 1, or 3b) followed by the keys of the images for that page
    ratios: a dict mapping image key to the image's apect ratio

    Returns:
    A string representing the html for that album
  """
  html = ""
  account = album_key.parent().get()
  image_keys = album_key.get().images
  letters = ["a", "b", "c"]
  patterns = ["dots", "diamonds", "stripes", "circles", "waves", "vStripes", "argyle"]
  page_num = 0
  for page in pages:
    page_imgs = page[1:]

    # Sets palette to gray if we're minimizing calls to Cloud Vision
    if MINIMIZE_BILLING:
      palette = [[128, 128, 128], [128, 128, 128], [128, 128, 128], [128, 128, 128]]
      stickers = []
    else:
      (palette, stickers) = get_details_from_cloud_vision(account, album_key.urlsafe(), page_imgs)
    
    div_class = "%s %s" % (page[0], random.choice(patterns))
    if stickers:
        # Picks a random sticker from those found
        div_class += " sticker %s" % random.choice(stickers)

    img_tags = ""

    for image in page_imgs:
        i = page_imgs.index(image)
        image_url = images.get_serving_url( image, size=300)
        logging.info(image_url)
        img_tags += """<div class='resizer' style='grid-area:%s;'> <img src='%s' style ='color: rgb%s'/> </div>""" % (letters[i], image_url, str(tuple(palette[i])))

    style = ""

    r = map(lambda x: ratios[x], page_imgs)
    if page[0] == "3a": #ttw
        columns = "%dfr %dfr" % ( int(100*(1/r[0] + .5 )/((1/r[0])+(1/r[1]) + 1 ) ), int(100*(1/r[1] + .5)/((1/r[0])+(1/r[1]) + 1) ) )
        rows = "%dfr %dfr" % ( 60, 40 )

        style = """
            grid-template-rows: %s;
            grid-template-columns: %s;
            grid-template-areas: "a b" "c c";
            """ % (rows, columns)

    elif page[0] == "3b": #tww
        rows = "%dfr %dfr" % ( int(100*(r[1]+ .5)/(r[1]+r[2] + 1)) , int(100*(r[2] + .5) /(r[1]+r[2] + 1)) )
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

    page_id = "id%d" % page_num
    page_num += 1
    html += """<div class='page' id='%s'>
                    <div class='album_square'>
                        <div class='container %s' style='%s'>
                            %s
                        </div>
                    </div>
                </div>""" % (page_id, div_class, style, img_tags)

  logging.info("Generated html: " + html)

  return html

def check_cloud_vision_cache_for_img(account, album_key, img_key):
    """ Checks cloud storage to see if there is a cloud vision response cached for the given image.

      Args:
      account: an Account entity
      album_key: the url safe version of an Album entity key
      img_key: a blob key

      Returns:
      The tuple (found, data). If a response was cached, then found is true. If no response was found,
      found is false and data is empty. Data is the string representation of a dictionary with keys:
        colors: top num_colors (see get_details_from_cloud_vision()) for the image based on score
        labels: top 5 labels for the image based on score
        landmark: top landmark name
      """
    filename = get_vision_cache_filename(account, album_key, img_key)
    (found, data) = get_file_from_cloud_storage(filename)
    logging.info("Data before reformatting: " + str(data))
    if found:
      #data = data.replace("'", "\"")
      data = ast.literal_eval(data)

    logging.info("Data is: " + str(data))
    return (found, data)

def cache_cloud_vision_results_for_img(account, album_key, img_key, results):
    """ Saves the already-parsed/processed results from cloud vision to cloud storage to avoid
        repeating cloud vision calls unnecessarily.

      Args:
      account: an Account entity
      album_key: the url safe version of an Album entity key
      img_key: a blob key
      results: a map containing colors, labels, and landmark information
    """
    filename = get_vision_cache_filename(account, album_key, img_key)
    upload_text_file_to_cloudstorage(filename, str(results))

def make_cloud_vision_api_call(requests):
    """ Makes a call to the google cloud vision api with the given payload. This is used to
      simplify the batched vs single-image request logic in get_details_from_cloud_vision.

      Args:
      requests: a list of requests to google cloud vision each containing an "image" key and "features" key

      Returns:
      A response containing the list of responses
     """
    logging.info("Making api call to cloud vision with %d requests" % (len(requests)))
    with open("config.yaml", 'r') as stream:
        config = yaml.load(stream)

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
    #logging.info("Str representation of what I'm returning: " + str(results[u'responses']))
    logging.info("Results to return from make_cloud_vision_api_call: %s" % (str(results)))
    return results[u'responses']


def get_details_from_cloud_vision(account, album_key, image_keys):
    """ Gets color, landmark, and label information for a page of images.

    Args:
    account: an Account entity
    album_key: the url_safe version of an Album key
    image_keys: A list of image blob keys

    Returns:
    The tuple (palette, stickers) where palette is a list of colors of the form:
    [ [r, g, b], [r, g, b] ... ]
    and stickers is a list of strings representing the potential stickers found
    for the set of images given
    """
    urlfetch.set_default_fetch_deadline(600)

    # logging.info("Going to arbitrarily throw an exception here...")
    # raise Exception("Random exception I'm throwing!")

    COMMON_LANDMARKS = ["eiffel tower", "statue of liberty", "taj mahal", "golden gate bridge"]
    COMMON_LABELS = ["dog", "cat", "beach", "christmas", "valentine", "heart", "easter", "winter", "snow"]

    # Description of the variables below:
    # results: list of responses from cloud vision (excludes cached responses)
    # cached_results: dict of image_keys to cached colors, labels, and landmark information for the image
    # requests: list of requests to send in the current payload
    # current_payload_img_size: size in bytes of the images currently in requests. These images will
    #     be sent as one request to cloud vision. The total payload size (images plus other request info)
    #     cannot exceed 8MB
    results = []
    cached_results = {}
    requests = []
    current_payload_img_size = 0

    for image_key in image_keys:
      (cached, cached_result) = check_cloud_vision_cache_for_img(account, album_key, image_key)
      if cached:
        logging.info("Image with key %s had a cached result. Result was: %s" % (str(image_key), str(cached_result)))
        cached_results[image_key] = cached_result
        continue

      logging.info("Image with key %s did not have a cached result. Going to call Vision API" % (str(image_key)))
      data = blobstore.BlobReader(image_key).read()
      img_size = len(data)
      logging.info("Current image size: %d. Payload size so far: %d" % (img_size, current_payload_img_size))

      # Estimate for 8MB (underestimate based on experience). Starts new payload if current image
      # cannot fit inside the current payload
      if (current_payload_img_size + img_size) >= (7800000):
          logging.info("Image with size %d was too big to fit in payload with current size %d. Starting new batch" % (img_size, current_payload_img_size))
          results.extend(make_cloud_vision_api_call(requests))

          current_payload_img_size = 0
          requests = []

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
      current_payload_img_size += img_size

    if requests:
        results.extend(make_cloud_vision_api_call(requests))

    logging.info("Str representation of the final aggregated results: %s. Cached results: %s" % (str(results), str(cached_results)))

    rgb_colors = []
    reds = []
    greens = []
    blues = []
    stickers = []

    # i is the current index into the results array (responses from cloud vision, not cached)
    i = 0
    for image_key in image_keys:
      if image_key in cached_results:
        colors = cached_results[image_key]["colors"]
        labels = cached_results[image_key]["labels"]
        landmark = cached_results[image_key]["landmark"]
      else:
        try:
          if len(image_keys) == 1:
            num_colors = 3
          elif len(image_keys) == 2:
            num_colors = 2
          else:
            num_colors = 1
          colors = results[i][u'imagePropertiesAnnotation'][u'dominantColors'][u'colors']
          colors = sorted(colors, key = lambda color : 0 * color[u'pixelFraction'] + color[u'score'] , reverse = True)[0:num_colors]
        except KeyError:
          colors = []

        try:
          labels = results[i][u'labelAnnotations']
          labels = sorted(labels, key = lambda annotation : annotation[u'score'] , reverse = True)[0:5]
          labels = [label[u'description'] for label in labels]
        except KeyError:
          labels = []

        try:
          landmark = results[i][u'landmarkAnnotations']
          landmark = sorted(landmark, key = lambda annotation : annotation[u'score'] , reverse = True)[0]
          landmark = landmark[u'description']
        except KeyError:
          landmark = ""
        i += 1

      for main_color in colors:
        info = main_color[u'color']
        rgb = [info[u'red'], info[u'green'], info[u'blue']]
        reds.append(rgb[0])
        greens.append(rgb[1])
        blues.append(rgb[2])
        rgb_colors.append(rgb)

      logging.info("Length of stickers so far: " + str(len(stickers)))

      for label in labels:
        if label in COMMON_LABELS:
          stickers.append(label)

      if landmark.lower() in COMMON_LANDMARKS:
        stickers.append(landmark)

      if image_key not in cached_results:
        results_to_cache = { "colors" : colors, "labels" : labels, "landmark" : landmark }
        logging.info("Image with key %s was not cached, so caching the results now... Content will be: %s" % (str(image_key), str(results_to_cache)))
        cache_cloud_vision_results_for_img(account, album_key, image_key, results_to_cache)

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

    # color at index 3 will be the background color of the page. This check here is to
    # catch the case where a grayscale image gets a super bright background
    is_grayscale = []
    for i in xrange(0, len(reds)):
      if abs(reds[i] - greens[i]) <= 25 and abs(reds[i] - blues[i]) <= 25 and abs(greens[i] - blues[i]) <= 25:
        logging.info("Determined that color with rgb %d, %d, %d is grayscale" % (reds[i], greens[i], blues[i]))
        is_grayscale.append(True)
      else:
        logging.info("Determined that color with rgb %d, %d, %d is NOT grayscale" % (reds[i], greens[i], blues[i]))
        is_grayscale.append(False)

    # If there were only two images, it's actually at the fifth index
    bg_color_index = 4 if len(image_keys) == 2 else 3
    [red, green, blue] = palette[bg_color_index]
    # if not (abs(red - green) <= 25 and abs(red - blue) <= 25 and abs(green - blue) <= 25):
    #   logging.info("Determined that the background color (%d, %d, %d) was too vibrant, resorting to average (%d, %d, %d)" % (
    #       palette[bg_color_index][0], palette[bg_color_index][1], palette[bg_color_index][2], average_rgb[0], average_rgb[1], average_rgb[2]))
    #   palette[bg_color_index] = average_rgb

    corrected_palette = [];
    for color in palette:
        corrected_palette.append(desaturate(color))
    return (corrected_palette, stickers)

def send_album_email(name, email, album_key):
    album = get_album_by_key(album_key)
    title = album.title
    url = "lazycloudalbum.appspot.com/view/%s" % (album_key)

    mail.EmailMessage(
            sender="noreply@lazycloudalbum.appspotmail.com",
            subject= "%s has been built!" %(title),
            to = "<%s>" % email,
            body = """
            Hey %s,

            We've finished putting together your '%s' album.

            Check it out here : %s
            """ % (name, title, url) ,
            html = """ <html><head></head><body>
            Hey %s,
            <br/>
            <br/>
            We've finished putting together your '%s' album.
            <br/>
            <br/>
            <a href = '%s'> Check it out! </a>
            </body>
            </html>
            """ % (name, title, url)
            ).Send()

def send_failure_email(name, email, title):
    mail.EmailMessage(
            sender="noreply@lazycloudalbum.appspotmail.com",
            subject= "%s failed to build." %(title),
            to = "<%s>" % email,
            body = """
            Hey %s,

            Something went wrong while we were putting together %s and we're unable to finish building it.

            It has been automatically deleted and will not show up in your albums.

            If this problem persists, please contact us!
            """ % (name, title) ,
            html = """ <html><head></head><body>
            Hey %s,
            <br/>
            <br/>
            Something went wrong while we were putting together %s and we're unable to finish building it.
            <br/>
            It has been automatically deleted and will not show up in your albums.
            <br/>
            If this problem persists, please contact us!
            </body>
            </html>
            """ % (name, title)
            ).Send()

def desaturate(color):
    new_color = color
    avg = sum(color)/3
    diffs = map(lambda x: abs(x-avg) , color)
    sum_diffs = sum(diffs)
    if sum_diffs > 50:
        a = (float(sum_diffs-50)/100)**2
        logging.info(a)
        new_color = map(lambda x:int((x+a*avg)/(1+a)), color)
        logging.info("%s might be bright, trying %s" % (str(color), str(new_color)))
    return new_color
