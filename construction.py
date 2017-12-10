import webapp2
import utils
import logging
import threading

from google.appengine.api import images
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.blobstore import BlobKey
from google.appengine.api.taskqueue import taskqueue
from PIL import Image

class Construct(webapp2.RequestHandler):
    def post(self):
        retry_count = int(self.request.headers.get("X-AppEngine-TaskRetryCount"))
        logging.info("Number of retries: " + str(retry_count))

        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        user = album.key.parent().get()

        # max tries we want to allow is 5
        if retry_count >= 3:
            # Deletes album. Parent checks aren't needed (I think) because the delete request is coming from
            # us, not from the user
            album.hidden = True
            album.put()
            task = taskqueue.add(
               url='/delete',
               params={'album': album_key},
               target = 'worker')

            # TODO: Need to send email about the album failing to build
            logging.error("FAILED TO BUILD ALBUM WITH NAME: " + album.title + ". ORDINARILY AN EMAIL WOULD BE SENT HERE")
            return
        
        ratio = {}
        shape = {}
        imgs = album.images
        for image_file in imgs:
            img = Image.open(blobstore.BlobReader(image_file))
            (w, h) = img.size
            p_ratio = float(h)/float(w)
            ratio[image_file] = p_ratio
            if p_ratio < 1 :
                shape[image_file] = "w" #wide
            elif p_ratio > 1 :
                shape[image_file] = "t" #tall
            else:
                shape[image_file] = "s" #square

        pages = []
        cursor = 0 #starts at 0
        while (cursor < len(imgs)):
            if (cursor + 3) <= len(imgs):
                imgs_for_page = sorted( [ imgs[cursor], imgs[cursor+1], imgs[cursor+2] ], key = lambda x: shape[x])
                shapes = map(lambda x : shape[x], imgs_for_page)
                if shapes == ["t","t","w"] or shapes == ["s","s","w"]:
                    pages.append( ["3a"] + imgs_for_page )
                    cursor += 3
                    continue
                elif shapes == ["t", "w", "w"] or shapes ==["t","s","s"]:
                    pages.append( ["3b"] + imgs_for_page )
                    cursor += 3
                    continue
            if (cursor + 2) <= len(imgs):
                imgs_for_page = sorted( [ imgs[cursor], imgs[cursor+1] ], key = lambda x: shape[x])
                shapes = map(lambda x : shape[x], imgs_for_page)
                if shapes == ["t","t"]:
                    pages.append( ["2a"] + imgs_for_page )
                    cursor += 2
                    continue
                elif shapes == ["w", "w"]:
                    pages.append( ["2b"] + imgs_for_page )
                    cursor += 2
                    continue
            pages.append( ["1"] + [imgs[cursor]] )
            cursor += 1

        logging.info("Going to generate the html now...")
        html = utils.generate_html(album.key, pages, ratio)
        logging.info("Done generating html! Saving html file now for user %s and album %s..." % (user.user_id, album_key))
        filename = utils.get_html_filename(user, album.key.urlsafe())
        utils.upload_text_file_to_cloudstorage(filename, html)
        logging.info("Done saving html file! Marking album as ready now...")
        album.ready = True
        album.put()

        try:
            utils.send_album_email(self.request.get("name"), self.request.get("email"), "Album")
        except:
            pass
        logging.info("Marked album as ready!")

class Delete(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        logging.info("Deleting album with key %s" % (album.key.urlsafe()))
        utils.clear_album_data(album)
        album.key.delete()

application = webapp2.WSGIApplication([(r'/construction', Construct), (r'/delete', Delete) ], debug=True)
