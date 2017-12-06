import webapp2
import utils
import logging

from google.appengine.api import images
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.blobstore import BlobKey
from PIL import Image

class Construct(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        user = album.key.parent().get()
        ratio = {}
        shape = {}
        imgs = album.images
        for image_file in imgs:
            img = Image.open(blobstore.BlobReader(image_file))
            (w, h) = img.size
<<<<<<< HEAD
            logging.info(img.size)
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
        logging.info(pages)
        logging.info(shape)
=======
            # logging.info(h)
            ratio[image_file] = float(h)/float(w)
>>>>>>> 4da4996bc98102b2ddbe2bb2ad0e74cb491fe28d
        logging.info(ratio)

        account = album.key.parent().get()
        html = utils.generate_html(album.key, pages, ratio)
        filename = utils.get_html_filename(account, album.key.urlsafe())
        utils.upload_text_file_to_cloudstorage(filename, html)
        #utils.send_album_email("mrgnmcsmith@gmail.com", "Album")

class Delete(webapp2.RequestHandler):
    @ndb.transactional
    def post(self):
        album_key = self.request.get("album")
        album = utils.get_album_by_key(album_key)
        utils.clear_album_data(album)
        album.key.delete()

application = webapp2.WSGIApplication([(r'/construction', Construct), (r'/delete', Delete) ], debug=True)
