import webapp2
import models
import os
import logging

import sys
sys.path.append('lib')

import cloudstorage as gcs
from PIL import Image
from datetime import datetime
from cStringIO import StringIO
from google.appengine.ext import ndb
from google.appengine.api import files, images
#from google.cloud import storage
from google.appengine.ext import blobstore


class BuildPage(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self):
        title = str(self.request.get('title'))
        

        account = models.get_account()
        album = models.Album( parent = account.key)


        file_img = self.request.get('file')
        if not file_img:
            logging.error('No image uploaded.')
            image_link = None
        else:
            img_str = StringIO(file_img)
            contents = img_str.getvalue()
            try:
                img = Image.open(img_str)
            except IOError, e:
                logging.error('%s', e)


            logging.info('FORMAT: %s', img.format)
            if img.format == 'JPEG':
                content_type = 'image/jpeg'
            elif img.format == 'PNG':
                content_type = 'image/png'
            else:
                logging.error('Unknown format: %s', img.format)
                content_type = 'text/plain'

            image_name = self.request.params['file'].filename
            logging.info('Uploading file "%s"...', image_name)
            if image_name.find('.'):
                image_name = image_name[:image_name.find('.')]

            filename = '/%s/%s_%s' % ("lazycloudalbum.appspot.com",
                                      image_name,
                                      datetime.strftime(datetime.now(), '%Y_%M_%d_%H_%M_%S'))
            
            gcs_file = gcs.open(filename,
                        'w',
                        content_type=content_type)

            gcs_file.write(contents)
            gcs_file.close()

            bucket = 'lazycloudalbum.appspot.com'
            object_name = filename

            gcs_image_location = '/gs/%s/%s' % (bucket, object_name)
            logging.info('gcs image location %s', gcs_image_location)
            #gcs_image_location = '/gs/%s' % (filename)

            blob_key = blobstore.create_gs_key(gcs_image_location)
            logging.info('blob key %s', blob_key)
            image_link = images.get_serving_url(blob_key) #, secure_url=True)
            #image_link = '/_ah%s' % gcs_image_location



        #client = storage.Client(project="lazycloudalbum")
        if title :
            album.title = title

        if image_link:
            album.html = image_link

        album.put()
        self.redirect('/')

application = webapp2.WSGIApplication([('/build', BuildPage)], debug=True)
