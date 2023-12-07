# coding=utf8
""" Blog Service

Handles all blog facing site requests
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-30"

# Ouroboros imports
from body import errors
from brain import access, users
from brain.users import details
from config import config
from tools import clone, evaluate, without

# Python imports
from base64 import b64decode, b64encode
import mimetypes
import os
import re
from time import time

# Pip imports
from redis import StrictRedis
from RestOC import Image, Services
from RestOC.Services import Error, internal_key, Response, Service
from RestOC.Record_MySQL import DuplicateException

# Errors
from .errors import NOT_AN_IMAGE, STORAGE_ISSUE

# Record classes
from .records import Category, CategoryLocale, Comment, Media, Post, \
	PostLocale, PostLocaleTag

# Figure out storage system
_storage_type = config.blog.storage('S3')
if _storage_type == 'S3':
	from .media.s3 import MediaStorage
else:
	raise ValueError('Storage type invalid', _storage_type)

class Blog(Service):
	"""Blog Service class

	Service for blog features
	"""

	_dimensions = re.compile(r'[cf][1-9]\d*x[1-9]\d*')
	"""Dimensions regex"""

	_image_extensions = ['jpeg', 'jpe', 'jpg', 'png']
	"""Valid image extensions"""

	def initialise(self):
		"""Initialise

		Initialises the instance and returns itself for chaining

		Returns:
			Blog
		"""

	def media_create(self, req: dict) -> Response:
		"""Media create

		Adds new media to the system for use in blog posts

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.CREATE)

		# Check minimum fields
		try: evaluate(req['data'], ['base64', 'filename'])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS,
				[ [ f, 'missing' ] for f in e.args ]
			)

		# Attempt to decode the file
		try:
			dFiles = {'source': b64decode(req['data'].pop('base64'))}
		except TypeError:
			return Services.Error(1001, [['base64', 'can not decode']])

		# Get the filename extension
		sExt = os.path.splitext(req['data']['filename'])[1][1:].lower()

		# If the file is an image
		dImage = None
		if sExt.lower() in self._image_extensions:

			# If dimensions were passed
			if 'thumbnails' in req['data']:

				# Get the node
				oNode = Media.get('image').get('thumbnails')

				# If they're valid, pop them off for later
				if oNode.valid(req['data']['thumbnails']):
					lThumbnails = req['data'].pop('thumbnails')

				# Else, return the errors
				else:
					return Error(errors.DATA_FIELDS, oNode.validation_failures)

			# We have no thumbnail requests, store an empty list
			else:
				lThumbnails = []

			# Attempt to get info about the photo
			try:
				dInfo = Image.info(dFiles['source'])
			except Exception as e:
				return Error(errors.DATA_FIELDS, [ [ 'base64', str(e.args) ] ])

			# Add the mime and length details to the req['data']
			req['data']['mime'] = dInfo['mime']
			req['data']['length'] = dInfo['length']

			# Init the image data
			dImage = {
				'resolution': dInfo['resolution'],
				'thumbnails': lThumbnails
			}

			# If additional dimensions were requested
			if lThumbnails:

				# Go through each additional dimension
				for s in lThumbnails:

					# Get the type and dimensions
					bCrop = s[0]
					sDims = s[1:]

					# Get a new image for the size
					dFiles[s] = Image.resize(dFiles['source'], sDims, bCrop)

		# Else, it's a regular file
		else:

			# Get the mime type based on the file name and store it
			tMime = mimetypes.guess_type(req['data']['filename'])
			req['data']['mime'] = (tMime[0] and tMime[0] or '')

			# Store the length as the bytes of the file
			req['data']['length'] = len(dFiles['source'])

		# Create an instance to validate the data
		try:
			if dImage:
				req['data']['image'] = dImage
			req['data']['_archived'] = False
			oFile = Media(req['data'])
		except ValueError as e:
			return Services.Error(1001, e.args[0])

		# Create the record
		if not oFile.create(
			changes = { 'user': req['session']['user']['_id'] }
		):

			# Record failed to be created
			return Services.Error(errors.DB_CREATE_FAILED)

		# Init the urls
		dURLs = {}

		# Go through each file generated
		for sRes in dFiles:

			# Get the filename
			sFilename = oFile.filename(sRes)

			# Create new object and upload it
			if not MediaStorage.save(sFilename, dFiles[sRes], oFile['mime']):

				# Delete the file
				oFile.delete(changes = { 'user': users.SYSTEM_USER_ID })

				# Delete each S3 file that was created
				for sRes in dURLs:
					MediaStorage.delete(oFile.filename(sRes))

				# Return the error
				return Services.Error(
					STORAGE_ISSUE,
					MediaStorage.last_error()
				)

			# Store the URL
			dURLs[sRes] = MediaStorage.url(sFilename)

		# Get the raw info
		dFile = oFile.record()

		# Add the URLs to the photo
		dFile['urls'] = dURLs

		# Return the file
		return Response(dFile)

	def media_delete(self, req: dict) -> Response:
		"""Media delete

		Removes media

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.DELETE)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS)

		# Find the file
		oFile = Media.get(req['data']['_id'])
		if not oFile:
			return Services.Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'media' ]
			)

		# Create a list of all the keys to delete off S3
		lFilenames = []

		# If it's an image
		if 'image' in oFile and oFile['image']:

			# Generate keys for each thumbnail
			for s in oFile['image']['thumbnails']:
				lFilenames.append(oFile.filename(s))

		# Add the main file
		lFilenames.append(oFile.filename())

		# Go through each key and delete the file
		for s in lFilenames:
			if not MediaStorage.delete(s):
				return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Delete the record and return the result
		return Services.Response(
			oFile.delete(changes = {'user': req['session']['user']['_id']})
		)

	def media_filter_read(self, req: dict) -> Response:
		"""Media Filter read

		Fetches existing media based on filtering info

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.READ)

		# Init filter
		dFilter = {}

		# If we have a range
		if 'range' in req['data']:
			dFilter['range'] = [
				int(req['data']['range'][0]),
				int(req['data']['range'][1])
			]

		# If we have a filename
		if 'filename' in req['data'] and req['data']['filename']:
			dFilter['filename'] = str(req['data']['filename'])

		# If we have a 'mine' filter
		if 'mine' in req['data']:
			dFilter['mine'] = req['session']['user']['_id']

		# If there's no filter
		if not dFilter:
			return Error(errors.DATA_FIELDS, [ [ 'range', 'missing' ] ])

		# Fetch and return the media
		return Response(
			Media.filter(dFilter)
		)

	def media_read(self, req: dict) -> Response:
		"""Media read

		Fetches an existing media and returns the data as well as the content \
		formatted as base64

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.READ)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS)

		# Find the file
		dFile = Media.get(req['data']['_id'], raw = True)
		if not dFile:
			return Services.Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'media' ]
			)

		# Generate the filaname
		sFilename = Media._filename(dFile)

		# Get the raw data
		sRaw = MediaStorage.open(sFilename)
		if sRaw is None:
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Convert it to base64 and add it to the data
		dFile['base64'] = b64encode(sRaw)

		# Return the file
		return Services.Response(dFile)

	def media_thumbnail_create(self, req: dict) -> Response:
		"""Media thumbnails create

		Adds a thumbnail to an existing file

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.UPDATE)

		# Check for fields
		try: evaluate(req['data'], [ '_id', 'size' ])
		except ValueError as e:
			return Error(errors.DATA_FIELDS, e.args)

		# Validate the size
		if not self._dimensions.match(req['data']['size']):
			return Error(errors.DATA_FIELDS, [ [ 'size', 'invalid' ] ])

		# Find the record
		oFile = Media.get(req['data']['_id'])
		if not oFile:
			return Error(errors.DB_NO_RECORD, [ req['data']['_id'], 'media' ])

		# If the file is not an image
		if 'image' not in oFile or not oFile['image']:
			return Error(NOT_AN_IMAGE, req['data']['_id'])

		# If the thumbnail already exists
		if req['data']['size'] in oFile['image']['thumbnails']:
			return Error(
				errors.DB_DUPLICATE,
				[ req['data']['_id'], req['data']['size'], 'media_thumbnail' ]
			)

		# Fetch the raw data
		sImage = MediaStorage.open(oFile.filename())
		if not sImage:
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Get the type of resize and the dimensions
		bCrop = req['data']['size'][0] == 'c'
		sDims = req['data']['size'][1:]

		# Generate a new thumbnail
		sThumbnails = Image.resize(sImage, sDims, bCrop)

		# Store it
		if not MediaStorage.save(
			oFile.filename(req['data']['size']), sThumbnails, oFile['mime']
		):
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Update the thumbnails
		dImage = clone(oFile['image'])
		dImage['thumbnails'].append(req['data']['size'])

		# Update the record, return the result
		oFile['image'] = dImage
		return Response(
			oFile.save(changes = {'user': req['session']['user']['_id']})
		)

	def media_thumbnail_delete(self, req: dict) -> Response:
		"""Media thumbnails delete

		Removes a thumbnail from an existing file

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.UPDATE)

		# Check for fields
		try: evaluate(req['data'], [ '_id', 'size' ])
		except ValueError as e:
			return Error(errors.DATA_FIELDS, e.args)

		# Validate the size
		if not self._dimensions.match(req['data']['size']):
			return Error(errors.DATA_FIELDS, [ [ 'size', 'invalid' ] ])

		# Find the record
		oFile = Media.get(req['data']['_id'])
		if not oFile:
			return Error(errors.DB_NO_RECORD, [ req['data']['_id'], 'media' ])

		# If the file is not an image
		if 'image' not in oFile or not oFile['image']:
			return Error(NOT_AN_IMAGE, req['data']['_id'])

		# If the thumbnail doesn't exist
		if req['data']['size'] not in oFile['image']['thumbnails']:
			return Response(False)

		# Delete it
		if not MediaStorage.delete(oFile.filename(req['data']['size'])):
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Update the thumbnails
		dImage = clone(oFile['image'])
		dImage['thumbnails'].remove(req['data']['size'])

		# Update the record, return the result
		oFile['image'] = dImage
		return Response(
			oFile.save(changes = {'user': req['session']['user']['_id']})
		)

	def media_url_read(self, req: dict) -> Response:
		"""Media URL read

		Returns the URL for a specific media file (or a thumbnail)

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_media', access.READ)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS)

		# Find the file
		dFile = Media.get(req['data']['_id'], raw = True)
		if not dFile:
			return Services.Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'media' ]
			)

		# If there's a size
		if 'size' in req['data']:

			# If the file is not an image
			if 'image' not in dFile or not dFile['image']:
				return Error(NOT_AN_IMAGE, req['data']['_id'])

			# If the size doesn't exist
			if req['data']['size'] not in dFile['image']['thumbnails']:
				return Error(
					errors.DB_NO_RECORD,
					[ '%s.%s' % (req['data']['_id'], req['data']['size']),
						'media_thumbnail' ]
				)

			# Generate the URL
			sURL = MediaStorage.url(Media._filename(dFile, req['data']['size']))

		# Else, just get the source
		else:

			# Generate the source URL
			sURL = MediaStorage.url(Media._filename(dFile))

		# Return the URL
		return Response(sURL)