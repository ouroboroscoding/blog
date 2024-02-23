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
from body import constants, errors
from brain import access, users
from brain.users import details
from config import config
from tools import clone, evaluate, without

# Python imports
from base64 import b64decode, b64encode
from copy import copy
import mimetypes
import os
import re
from time import time

# Pip imports
from redis import StrictRedis
from RestOC import Image, Services
from RestOC.Services import Error, Response, Service
from RestOC.Record_MySQL import DuplicateException, Literal

# Errors
from blog.errors import MINIMUM_LOCALE, NOT_AN_IMAGE, POSTS_ASSOCIATED, \
	STORAGE_ISSUE

# Record classes
from blog.records import cache as record_cache, Category, CategoryLocale, \
	Comment, Media, Post, PostCategory, PostRaw, PostTag

# Figure out storage system
_storage_type = config.blog.storage('S3')
if _storage_type == 'S3':
	from blog.media.s3 import MediaStorage
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

		# Get config
		self._conf = config.blog({
			'user_default_locale': 'en-US',
			'redis_host': 'blog'
		})

		# Create a connection to Redis
		self._redis = StrictRedis(**config.redis[self._conf['redis_host']]({
			'host': 'localhost',
			'port': 6379,
			'db': 0
		}))

		# Pass the Redis connection to the records
		record_cache(self._redis)

		# Return self for chaining
		return self

	def admin_category_create(self, req: dict) -> Response:
		"""Category create

		Adds a new category to the system for use in blog posts

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.CREATE)

		# Check minimum fields
		try: evaluate(req['data'], [{'record': ['locales']}])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# Get the record
		dRecord = req['data']['record']

		# If locales exists but is empty
		if not dRecord['locales']:
			return Error(
				errors.DATA_FIELDS, [ [ 'record.locales', 'missing' ] ]
			)

		# If it exists but is not a dict
		if not isinstance(dRecord['locales'], dict):
			return Error(
				errors.DATA_FIELDS, [ [ 'record.locales', 'invalid' ] ]
			)

		# Go through each passed locale
		lLocales = []
		for k,d in dRecord['locales'].items():

			# Add the empty UUID so we don't fail on the `_category` check
			d['_category'] = constants.EMPTY_UUID

			# Add the locale as a field
			d['_locale'] = k

			# Verify the fields
			try:
				lLocales.append(CategoryLocale(d))
			except ValueError as e:
				return Error(
					errors.DATA_FIELDS,
					[ [ 'record.locale.%s.%s' % (k, l[0]), l[1] ] \
						for l in e.args[0] ]
				)

			# Make sure we don't already have the slug
			if CategoryLocale.exists(d['slug'], 'slug'):
				return Error(
					errors.DB_DUPLICATE, [ '%s.%s' % (k, d['slug']), 'slug' ]
				)

		# Create the instance
		oCategory = Category({})

		# Create the record
		if not oCategory.create(changes = {
			'user': req['session']['user']['_id']
		}):
			return Error(errors.DB_CREATE_FAILED, 'category')

		# Create each locale
		for o in lLocales:

			# Add the real category ID
			o['_category'] = oCategory['_id']

			# Create the record
			try:
				o.create(changes = { 'user': req['session']['user']['_id'] })
			except DuplicateException as e:

				# Delete the existing category and any locales that were
				#	created
				oCategory.delete(
					changes = { 'user': req['session']['user']['_id'] }
				)
				for o2 in lLocales:
					if o2['_id']:
						o2.delete(
							changes = { 'user': req['session']['user']['_id'] }
						)

				# Return the duplicate error
				return Error(errors.DB_DUPLICATE, [ o['slug'], 'slug' ])

		# Return the new ID
		return Response(oCategory['_id'])

	def admin_category_delete(self, req: dict) -> Response:
		"""Category delete

		Removes an existing category from the system

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.DELETE)

		# If we didn't get an ID
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ '_id', 'missing' ] ])

		# Fetch the category
		oCategory = Category.get(req['data']['_id'])
		if not oCategory:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'category' ]
			)

		# If there's any posts associated with this category let the user
		#	know we can't delete it
		lPosts = PostCategory.filter({
			'_category': req['data']['_id']
		}, raw = [ '_id' ])
		if lPosts:
			return Error(POSTS_ASSOCIATED, [ d['_id'] for d in lPosts ])

		# Get the associated locales
		lLocales = CategoryLocale.filter({
			'_category': req['data']['_id']
		})

		# Delete each one
		for o in lLocales:
			if not o.delete(
				changes = { 'user': req['session']['user']['_id'] }
			):

				# If it failed for any reason
				return Error(
					errors.DB_DELETE_FAILED, [ o['_id'], 'category_locale' ]
				)

		# Delete the record
		if not oCategory.delete(
			changes = { 'user': req['session']['user']['_id'] }
		):
			# If it failed for any reason
			return Error(
				errors.DB_DELETE_FAILED, [ req['data']['_id'], 'category' ]
			)

		# Return OK
		return Response(True)

	def admin_category_locale_create(self, req: dict) -> Response:
		"""Category Locale create

		Creates a new locale record associated with a category

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.UPDATE)

		# Check minimum fields
		try: evaluate(req['data'], ['_id', 'locale', 'record' ])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# If the category doesn't exist
		if not Category.exists(req['data']['_id']):
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'category ']
			)

		# Store the record
		dRecord = req['data']['record']

		# Create the instance
		try:
			dRecord['_category'] = req['data']['_id']
			dRecord['_locale'] = req['data']['locale']
			oLocale = CategoryLocale(dRecord)
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS,
				[ [ 'record.%s' % l[0], l[1] ] for l in e.args[0] ]
			)

		# Create the record
		try:
			oLocale.create(changes = { 'user': req['session']['user']['_id'] })
		except DuplicateException as e:
			if e.args[1] == 'slug':
				return Error(
					errors.DB_DUPLICATE, [ dRecord['slug'], 'slug' ]
				)
			elif e.args[1] == '_locale':
				return Error(
					errors.DB_DUPLICATE, [ dRecord['locale'], 'locale' ]
				)
			else:
				return Error(errors.DB_DUPLICATE, 'unknown')

		# Return OK
		return Response(True)

	def admin_category_locale_delete(self, req: dict) -> Response:
		"""Category Locale delete

		Deletes an existing locale record associated with a category

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.UPDATE)

		# Check minimum fields
		try: evaluate(req['data'], ['_id', 'locale' ])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# If the category doesn't exist
		if not Category.exists(req['data']['_id']):
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'category ']
			)

		# Get the count of existing category locales
		iCount = CategoryLocale.count(filter = {
			'_category': req['data']['_id']
		})

		# If there's less than 2
		if iCount < 2:
			return Error(MINIMUM_LOCALE)

		# Else, find the record
		oLocale = CategoryLocale.filter({
			'_category': req['data']['_id'],
			'_locale': req['data']['locale']
		}, limit = 1)
		if not oLocale:
			return Error(errors.DB_NO_RECORD)

		# Delete the record
		if not oLocale.delete(
			changes = { 'user': req['session']['user']['_id'] }
		):
			return Error(errors.DB_DELETE_FAILED)

		# Return OK
		return Response(True)

	def admin_category_locale_update(self, req: dict) -> Response:
		"""Category Locale update

		Updates an existing locale record associated with a category

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.UPDATE)

		# Check minimum fields
		try: evaluate(req['data'], ['_id', 'locale', 'record' ])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# If the category doesn't exist
		if not Category.exists(req['data']['_id']):
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'category ']
			)

		# Store the record
		dRecord = req['data']['record']

		# Find the record
		oLocale = CategoryLocale.filter({
			'_category': req['data']['_id'],
			'_locale': req['data']['locale']
		}, limit = 1)
		if not oLocale:
			return Error(errors.DB_NO_RECORD)

		# Go through fields that can be changed
		lErrors = []
		for f,v in without(
			dRecord, ['_id', '_created', '_category', '_locale']
		).items():

			# Try to update the field
			try: oLocale[f] = v
			except ValueError as e:
				lErrors.extend([
					[ 'record.%s' % l[0], l[1] ] \
					for l in e.args[0]
				])

		# If there's any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Update the record
		if not oLocale.save(changes = { 'user': req['session']['user']['_id']}):
			return Error(errors.DB_UPDATE_FAILED)

		# Return OK
		return Response(True)

	def admin_category_read(self, req: dict) -> Response:
		"""Category read

		Fetches all data associated with one or all categories

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.READ)

		# If there's no ID passed
		if 'data' not in req or '_id' not in req['data']:

			# Fetch all locales
			lLocales = CategoryLocale.get(raw = True)

			# Store locales by category
			dLocales = {}
			for d in lLocales:

				# If the category doesn't exist
				if d['_category'] not in dLocales:
					dLocales[d['_category']] = {}

				# Add the locale
				dLocales[d['_category']][d['_locale']] = \
					without(d, [ '_category', '_locale' ])

			# Clear memory
			del lLocales

			# Fetch all categories
			lCategories = Category.get(raw = True)

			# Go through each one and add the locales
			for d in lCategories:
				try: d['locales'] = dLocales.pop(d['_id'])
				except KeyError:
					d['locales'] = {}

			# Return the data
			return Response(lCategories)

		# Else, we got a specific ID
		else:

			# Fetch the category
			dCategory = Category.get(req['data']['_id'], raw = True)
			if not dCategory:
				return Error(
					errors.DB_NO_RECORD, [ req['data']['_id'], 'category' ]
				)

			# Fetch all locales associated
			dCategory['locales'] = {
				d['_locale']: without(d, [ '_category', '_locale' ]) \
				for d in CategoryLocale.filter({
					'_category': req['data']['_id']
				}, raw = True)
			}

			# Return the data
			return Response(dCategory)

	def admin_category_update(self, req: dict) -> Response:
		"""Category update

		Updates all data associated with an existing category

		Arguments:
		req (dict): The request details, which can include 'data', \
			'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_category', access.UPDATE)

		# Check minimum fields
		try: evaluate(req['data'], [ '_id', { 'record': [ 'locales' ] } ])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# If it doesn't exist
		if not Category.exists(req['data']['_id']):
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'category' ]
			)

		# Get the data
		sID = req['data']['_id']
		dRecord = req['data']['record']

		# Init return result and errors
		bRes = False
		lErrors = []

		# Get all the associated locales for this category and store them by
		#	locale
		dLocales = {
			d['_locale']: d for d in CategoryLocale.filter({
				'_category': sID
			})
		}

		# Go through each locale
		for sLocale, dLocale in dRecord['locales']:

			# Init locale errors
			lLocaleErr = []

			# If we have it
			if sLocale in dLocales:

				# Go through fields that can be changed
				for f,v in without(dLocale, ['_id', '_created', '_locale']):
					try: dLocales[sLocale][f] = v
					except ValueError as e:
						lLocaleErr.extend([
							[ 'record.locales.%s.%s' % (sLocale, l[0]), l[1] ] \
							for l in e.args[0]
						])

				# If we any errors, extend the overall errors
				if lLocaleErr:
					lErrors.extend(lLocaleErr)

				# Else, try to save the locale
				else:
					if dLocales[sLocale].save(
						changes = { 'user': req['session']['_id'] }
					):
						bRes = True

			# Else, it must be new
			else:

				# Create the instance to test it
				try:

					# Add the locale and category to the data
					dLocale['_category'] = sID
					dLocale['_locale'] = sLocale
					oLocale = CategoryLocale(dLocale)

				# If there's any errors
				except ValueError as e:
					lLocaleErr.extend([
						[ 'record.locales.%s.%s' % (sLocale, l[0]), l[1] ] \
						for l in e.args[0]
					])

				# If we any errors, extend the overall errors
				if lLocaleErr:
					lErrors.extend(lLocaleErr)

				# Else, create the record
				else:
					try:
						if oLocale.create(
							changes = { 'user': req['session']['user']['_id']}
						):
							bRes = True
					except DuplicateException as e:
						return

		# If we have any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Return the result
		return Response(bRes)

	def admin_media_create(self, req: dict) -> Response:
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
				oNode = Media._conf['tree'].get('image').get('thumbnails')

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
					bCrop = s[0] == 'c'
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
			req['data']['uploader'] = req['session']['user']['_id']
			oFile = Media(req['data'])
		except ValueError as e:
			return Services.Error(1001, e.args[0])

		# Create the record
		try:
			if not oFile.create(
				changes = { 'user': req['session']['user']['_id'] }
			):

				# Record failed to be created
				return Services.Error(errors.DB_CREATE_FAILED)

		# If the file already exists
		except DuplicateException as e:
			return Error(errors.DB_DUPLICATE)

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

	def admin_media_delete(self, req: dict) -> Response:
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

	def admin_media_filter_read(self, req: dict) -> Response:
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

		# If we only want images
		if 'images_only' in req['data'] and req['data']['images_only']:
			dFilter['images_only'] = True

		# If there's no filter
		if not dFilter:
			return Error(errors.DATA_FIELDS, [ [ 'range', 'missing' ] ])

		# Get the records
		lRecords = Media.search(dFilter)

		# Go through each and add the URLs
		for d in lRecords:

			# Init the urls
			d['urls'] = { 'source': MediaStorage.url(Media._filename(d)) }

			# If we have an image, and we have thumbnails
			if 'image' in d and d['image'] and d['image']['thumbnails']:
				for s in d['image']['thumbnails']:
					d['urls'][s] = MediaStorage.url(Media._filename(d, s))

		# Return the records
		return Response(lRecords)

	def admin_media_read(self, req: dict) -> Response:
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

	def admin_media_thumbnail_create(self, req: dict) -> Response:
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

		# Generate the filename
		sFilename = oFile.filename(req['data']['size'])

		# Store it
		if not MediaStorage.save(sFilename, sThumbnails, oFile['mime']):

			# If it failed, return a standard storage error, plus the error from
			#	the specific storage engine
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Update the thumbnails
		dImage = clone(oFile['image'])
		dImage['thumbnails'].append(req['data']['size'])

		# Set the new image in the record
		oFile['image'] = dImage

		# Save the record and store the result
		bRes = oFile.save(changes = {'user': req['session']['user']['_id']})

		# If we failed to save the record
		if not bRes:
			return Error(errors.DB_UPDATE_FAILED)

		# Return the new URL
		return Response(
			MediaStorage.url(sFilename)
		)

	def admin_media_thumbnail_delete(self, req: dict) -> Response:
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

			# If it failed, return a standard storage error, plus the error from
			#	the specific storage engine
			return Error(STORAGE_ISSUE, MediaStorage.last_error())

		# Update the thumbnails in the image section
		dImage = clone(oFile['image'])
		dImage['thumbnails'].remove(req['data']['size'])

		# Set the new image in the record
		oFile['image'] = dImage

		# Save the record and store the result
		bRes = oFile.save(changes = {'user': req['session']['user']['_id']})

		# If we failed to save the record
		if not bRes:
			return Error(errors.DB_UPDATE_FAILED)

		# Return success
		return Response(True)

	def admin_media_url_read(self, req: dict) -> Response:
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

	def admin_post_create(self, req: dict) -> Response:
		"""Post create

		Creates a new Post

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.CREATE)

		# Make sure we have locales at minimum
		if 'locales' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ 'locales', 'missing' ] ])

		# Go through each locale
		for k in req['data']['locales']:

			# Make sure the slug doesn't already exist
			if Post.exists(req['data']['locales'][k]['slug']):
				return Error(
					errors.DB_DUPLICATE,
					[ req['data']['locales'][k]['slug'], 'slug' ]
				)

			# Check for the locale
			oResponse = Services.read('mouth', 'locale/exists', { 'data': {
				'_id': k
			}})

			# If it doesn't exist on mouth
			if not oResponse.data:
				return Error(
					errors.DB_NO_RECORD, [ k, 'locale' ]
				)

		# If there's any categories sent
		if 'categories' in req['data'] and req['data']['categories']:

			# Readability
			lCats = req['data']['categories']

			# Check the values are unique
			if len(set(lCats)) != len(lCats):
				return Error(
					errors.DATA_FIELDS, [ [ 'categories', 'not unique']]
				)

			# Get all the IDs
			lRecords = [ d['_id'] for d in Category.get(
				lCats, raw = [ '_id' ]
			) ]

			# If the counts don't match
			if len(lRecords) != len(lCats):
				return Error(
					errors.DB_NO_RECORD,
					[ [ c for c in lCats if c not in lRecords ], 'category' ]
				)

		# Test the values by making the raw post instance
		try:
			oPostRaw = PostRaw(req['data'])
		except ValueError as e:
			return Error(errors.DATA_FIELDS, e.args[0])

		# Create the instance and store the ID
		sID = oPostRaw.create(
			changes = { 'user': req['session']['user']['_id'] }
		)

		# If the record wasn't create
		if not sID:
			return Error(errors.DB_CREATE_FAILED, 'post_raw')

		# Return the new ID
		return Response(sID)

	def admin_post_delete(self, req: dict) -> Response:
		"""Post delete

		Deletes an existing Post

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.DELETE)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ '_id', 'missing' ] ])

		# Fetch the record
		oPostRaw = PostRaw.get(req['data']['_id'])

		# If it doesn't exist
		if not oPostRaw:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'post_raw' ]
			)

		# Get the slugs for each locale
		lSlugs = [d['slug'] for d in oPostRaw['locales'].values()]

		# Delete all categories associated
		PostCategory.delete_get(lSlugs, index = '_slug')

		# Delete all tags associated
		PostTag.delete_get(lSlugs, index = '_slug')

		# Delete all posts associated
		Post.delete_get(lSlugs)

		# Delete the post
		bRes = oPostRaw.delete(
			changes = { 'user': req['session']['user']['_id']}
		)

		# If the post wasn't deleted
		if not bRes:
			return Error(
				errors.DB_DELETE_FAILED, [ req['data']['_id'], 'post_raw' ]
			)

		# Return OK
		return Response(True)

	def admin_post_publish_update(self, req: dict) -> Response:
		"""Post Publish update

		Takes the current saved post and makes it the live version

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_publish', access.UPDATE)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ '_id', 'missing' ] ])

		# Fetch the raw post
		oRaw = PostRaw.get(req['data']['_id'])
		if not oRaw:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'post_raw' ]
			)

		# If the last published date is the same as the update date, then
		#	there's nothing to do here
		if oRaw['last_published'] and oRaw['last_published'] >= oRaw['_updated']:
			return Response(False)

		# Init the flag to know if anything actually changed
		bChanges = False

		# Init possible errors, a dict of slugs to locales, and a list of
		#	locales with tags that need to be regenerated
		lErrors = []
		lsTagLocales = set()
		lsPostsLocales = set()
		dLocalesTags = {}
		dSlugs = {}

		# Go through each locale
		for k in oRaw['locales']:
			if oRaw['locales'][k]['slug'] in dSlugs:
				lErrors.append(
					[ 'locales.%s.slug' % k, 'duplicate' ]
				)
			else:
				dSlugs[oRaw['locales'][k]['slug']] = k

		# If we didn't get a errors yet
		if not lErrors:

			# Check if any of the slugs exist on other posts
			lExisting = Post.get(list(dSlugs.keys()), filter = {
				'_raw': { 'neq': oRaw['_id'] }
			}, raw = [ '_slug' ])

			# If we got any posts at all, create an error item for each
			#	duplicate
			if lExisting:
				lErrors = [ [
					'locales.%s.slug' % dSlugs[d['_slug']],
					'duplicate'
				] for d in lExisting ]

		# If we got any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Get all the posts associated with this one, stored by slug
		dPosts = Post.by_raw(req['data']['_id'])

		# Init the lists of posts to create and of posts to update
		lCreate = []
		lUpdate = []

		# Go through each locale in the raw post
		for sLocale, dLocale in oRaw['locales'].items():

			# Make a unique id from the slug and locale
			sSlugLocale = '%s:%s' % (dLocale['slug'], sLocale)

			# Do we have this already
			if sSlugLocale in dPosts:

				# Remove the existing post and add it to the update list along
				#	side the raw, unpublished data
				lUpdate.append([
					dPosts.pop(sSlugLocale),
					dLocale
				])

			# Else, if we haven't published this locale yet, add it to the
			#	create list
			else:
				lCreate.append([sLocale, dLocale])

		# Do we have any published posts left?
		if dPosts:

			# Go through each post that no longer has a counterpoint in the raw
			#	data
			for d in dPosts:

				# Fetch all the tags that will be deleted
				lTags = [ d['tag'] for d in PostTag.filter({
					'_slug': d['_slug']
				}, raw = [ 'tag' ]) ]

				# If there's any
				if lTags:

					# Delete them
					PostTag.delete_get(d['_slug'], index = '_slug')

					# Add them to the corresponding locale
					try: dLocalesTags[d['_locale']].update(lTags)
					except KeyError: dLocalesTags[d['_locale']] = set(lTags)

				# Add the locale to the tag and posts lists so we regenerate
				#	them
				lsTagLocales.add(d['_locale'])
				lsPostsLocales.add(d['_locale'])

				# Delete all categories, tags, and the post itself based on the
				#	slug
				PostCategory.delete_get(d['_slug'], index = '_slug')
				Post.delete_get(d['_slug'])

				# Delete it from the cache
				Post.cache_delete(d['_slug'])

			# Something changed
			bChanges = True

		# If we have any posts to publish for the first time
		if lCreate:

			# Init the list of categories, of tags, and of posts
			lCategories = []
			lTags = []
			lPosts = []

			# Go through each locale to create
			for sLocale, dLocale in lCreate:

				# Add the post
				lPosts.append(Post({
					'_slug': dLocale['slug'],
					'_raw': oRaw['_id'],
					'_locale': sLocale,
					'title': dLocale['title'],
					'content': dLocale['content'],
					'meta': 'meta' in dLocale and dLocale['meta'] or {},
					'locales': oRaw.localesToSlugs(sLocale)
				}))

				# Extend the categories for each one found in the raw data
				lCategories.extend([ PostCategory({
					'_slug': dLocale['slug'],
					'_category': s
				}) for s in oRaw['categories'] ])

				# If we have tags in this post
				if dLocale['tags']:

					# Extend the tags for each one found in the raw data
					lTags.extend([ PostTag({
						'_slug': dLocale['slug'],
						'tag': s
					}) for s in dLocale['tags'] ])

					# Add them to the locale for regenerating
					try:
						dLocalesTags[sLocale].update(dLocale['tags'])
					except KeyError:
						dLocalesTags[sLocale] = set(dLocale['tags'])

					# Add the locale to the list to be regenerated
					lsTagLocales.add(sLocale)

				# Add the locale to the post list to be regenerated
				lsPostsLocales.add(d['_locale'])

			# Create the posts
			Post.create_many(lPosts)

			# If we have categories, create them
			if lCategories:
				PostCategory.create_many(lCategories)

			# If we have tags, create them
			if lTags:
				PostTag.create_many(lTags)

			# Add each post to the cache
			for d in lPosts:
				Post.cache_generate(d['_slug'])

			# Something changed
			bChanges = True

		# If we have any to update
		if lUpdate:

			# Go through each post to update
			for dPost, dLocale in lUpdate:

				# Remove the categories and tags
				lCategories = dPost.pop('categories').sort()
				lTags = dPost.pop('tags')

				# Create the Post instance
				oPost = Post(dPost)

				# Go through each field and update it
				for k in [ 'title', 'content', 'meta' ]:
					if k in dLocale:
						oPost[k] = dLocale[k]

				# Update the locale slugs
				oPost['locales'] = oRaw.localesToSlugs(dPost['_locale'])

				# Update the post
				if oPost.save():

					# Something changed
					bChanges = True

				# If the categories have changed
				if lCategories != sorted(oRaw['categories']):

					# Something changed
					bChanges = True

					# Delete the existing ones
					PostCategory.delete_get(dPost['_slug'], index = '_slug')

					# And add the new ones (if there are any)
					lNewCats = [ PostCategory({
						'_slug': dPost['_slug'],
						'_category': s
					}) for s in oRaw['categories'] ]
					if lNewCats:
						PostCategory.create_many(lNewCats)

				# If the tags have changed
				if lTags != dLocale['tags']:

					print('lTags: %s' % lTags)
					print('dLocale[\'tags\']: %s' % dLocale['tags'])

					# Something changed
					bChanges = True

					# Delete the existing ones
					PostTag.delete_get(dPost['_slug'], index = '_slug')

					# Add the deleted tags to the locale for regenerating
					try:
						dLocalesTags[oPost['_locale']].update(lTags)
					except KeyError:
						dLocalesTags[oPost['_locale']] = set(lTags)

					# And add the new ones (if there are any)
					lNewTags = [ PostTag({
						'_slug': dPost['_slug'],
						'tag': s
					}) for s in dLocale['tags'] ]
					if lNewTags:

						# Insert the new tags
						PostTag.create_many(lNewTags)

						# Add the new tags to the locale for regenerating
						try:
							dLocalesTags[oPost['_locale']].update(
								dLocale['tags']
							)
						except KeyError:
							dLocalesTags[oPost['_locale']] = \
								set(dLocale['tags'])

					# Add the locale to the list to be regenerated
					lsTagLocales.add(dPost['_locale'])

				# Update the post in the cache
				Post.cache_generate(oPost['_slug'])

				# Add the locale to the posts set
				lsPostsLocales.add(oPost['_locale'])

		# Go through each locale and regenerate the tags
		for sLocale in lsTagLocales:
			PostTag.all_locale_cache_generate(sLocale)

		# Go through each locale and regenerate the posts
		for sLocale in lsPostsLocales:
			Post.locale_cache_generate(sLocale)

		# Go through each locale and tag and regenerate the corresponding slugs
		for sLocale in dLocalesTags:
			for sTag in dLocalesTags[sLocale]:
				PostTag.locale_cache_generate(sTag, sLocale)

		# If anything got added, removed, or updated
		if bChanges:

			# Update the last published
			oRaw['last_published'] = Literal('CURRENT_TIMESTAMP')

			# Save the raw record
			if oRaw.save(changes = { 'user': req['session']['user']['_id'] }):
				return Response(True)

		# Return failure
		return Response(False)

	def admin_post_read(self, req: dict) -> Response:
		"""Post read

		Fetches an existing Post

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.READ)

		# If the ID is missing
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ '_id', 'missing' ] ])

		# Fetch the raw post
		dPostRaw = PostRaw.get(req['data']['_id'], raw = True)
		if not dPostRaw:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'post_raw' ]
			)

		# Return the post
		return Response(dPostRaw)

	def admin_post_unpublished_read(self, req: dict) -> Response:
		"""Post Unpublished read

		Returns all posts that have never been published, or have unpublished \
		changes

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.READ)

		# Fetch all the raw posts that have never been published, or whose
		#	last updated time is newer than the last published time, and return
		#	them
		return Response(
			PostRaw.unpublished()
		)

	def admin_post_update(self, req: dict) -> Response:
		"""Post update

		Updates an existing raw post

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.UPDATE)

		# Make sure we have the ID
		if '_id' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ '_id', 'missing' ] ])

		# Find the post
		oPost = PostRaw.get(req['data']['_id'])
		if not oPost:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['_id'], 'post_raw' ]
			)

		# Init possible errors
		lErrors = []

		# If we have categories
		if 'categories' in req['data']:

			# Readability
			lCats = req['data']['categories']

			# If we have any
			if lCats:

				# Check the values are unique
				if len(set(lCats)) != len(lCats):
					return Error(
						errors.DATA_FIELDS, [ [ 'categories', 'not unique']]
					)

				# Get all the IDs
				lRecords = [ d['_id'] for d in Category.get(
					lCats, raw = [ '_id' ]
				) ]

				# If the counts don't match
				if len(lRecords) != len(lCats):
					return Error(
						errors.DB_NO_RECORD,
						[ [ c for c in lCats if c not in lRecords ], 'category' ]
					)

			# Set categories
			try:
				oPost['categories'] = lCats
			except ValueError as e:
				lErrors.extend(e.args[0])

		# If we have locales
		if 'locales' in req['data']:

			# Set locales
			try:
				oPost['locales'] = req['data']['locales']

				# Go through each locale
				dSlugs = {}
				for k in oPost['locales']:
					if oPost['locales'][k]['slug'] in dSlugs:
						lErrors.append(
							[ 'locales.%s.slug' % k, 'duplicate' ]
						)
					else:
						dSlugs[oPost['locales'][k]['slug']] = k

				# If there's no errors within the post
				if not lErrors:

					# Check if any of them exist on other posts
					lPosts = Post.get(list(dSlugs.keys()), filter = {
						'_raw': { 'neq': oPost['_id'] }
					}, raw = [ '_slug' ])

					# If we got any
					if lPosts:
						for d in lPosts:
							lErrors.append([
								'locales.%s.slug' % dSlugs[d['_slug']],
								'duplicate'
							])

			except ValueError as e:
				lErrors.extend(e.args[0])

		# If we got any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Save the record and store the result
		bRes = oPost.save( changes = { 'user': req['session']['user']['_id'] })
		if not bRes:
			return Error(errors.DB_UPDATE_FAILED)

		# Return OK
		return Response(True)

	def admin_posts_read(self, req: dict) -> Response:
		"""Posts read

		Fetches and returns all published posts combined

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Make sure the user is signed in and has access
		access.verify(req['session'], 'blog_post', access.READ)

		# Init the dict of raw to locales
		dRaw = {}

		# Fetch all the published posts
		lPosts = Post.get(
			raw = [ '_raw', '_locale', '_created', '_updated', 'title' ],
			orderby = [ [ '_updated', 'DESC' ] ]
		)

		# Go through each post
		for d in lPosts:

			# Add it to the raw
			try:
				dRaw[d['_raw']]['locales'][d['_locale']] = \
					{ 'title': d['title'] }
			except KeyError: dRaw[d['_raw']] = {
				'_raw': d['_raw'],
				'_created': d['_created'],
				'_updated': d['_updated'],
				'locales': {
					d['_locale']: { 'title': d['title']}
				}
			}

		print(dRaw)

		# Return the values in the raw
		return Response(
			list(dRaw.values())
		)

	def category_read(self, req: dict) -> Response:
		"""Category read

		Finds the category by slug, then returns all the posts associated

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# If the slug is not passed
		if 'slug' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ 'slug', 'missing' ] ])

		# Find the category by slug
		dCategory = CategoryLocale.filter({
			'slug': req['data']['slug']
		}, raw = ['_category', '_locale', 'title', 'description' ], limit = 1)

		# If it doesn't exist, 404
		if not dCategory:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['slug'], 'category_locale' ]
			)

		# Find the other locale slugs and add them to the category
		dCategory['locales'] = {
			d['_locale']: d['slug'] \
			for d in CategoryLocale.filter({
				'_category': dCategory['_category'],
				'_locale': { 'neq': dCategory['_locale'] }
			}, raw = [ '_locale', 'slug' ]) }

		# Get all the associated posts and add them to the category
		dCategory['posts'] = Post.by_category(
			dCategory['_locale'],
			dCategory['_category']
		)

		# Return the category
		return Response(dCategory)

	def post_read(self, req: dict) -> Response:
		"""Post read

		Finds the post by slug, then returns all related info

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# If the slug is not passed
		if 'slug' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ 'slug', 'missing' ] ])

		# Fetch it by slug
		dPost = Post.cache_fetch(req['data']['slug'])

		# If it doesn't exist, 404
		if not dPost:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['slug'], 'post' ]
			)

		# Return the post
		return Response(dPost)

	def posts_read(self, req: dict) -> Response:
		"""Posts read

		Returns all posts on a specific page / count

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Init errors
		lErrors = []

		# If the locale is missing
		if 'locale' not in req['data']:
			lErrors.append([ 'locale', 'missing' ])

		# If the page is missing
		if 'page' not in req['data']:
			iPage = 1

		# Else, we got a page
		else:

			# Try to convert it
			try:
				iPage = int(req['data']['page'])
			except ValueError as e:
				lErrors.append([ 'page', 'invalid' ])

			# If it's less than 1, reject it
			if iPage < 1:
				lErrors.append([ 'page', 'invalid' ])

		# If the count is missing
		if 'count' not in req['data']:
			iCount = 10

		# Else, we got a count
		else:

			# Try to convert it
			try: iCount = int(req['data']['count'])
			except ValueError as e:
				lErrors.append([ 'count', 'invalid' ])

			# If it's less than 1, reject it
			if iPage < 1:
				lErrors.append([ 'count', 'invalid' ])

		# If there's any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Fetch and return the posts
		return Response(
			Post.locale_cache_fetch(
				req['data']['locale'],
				iPage - 1,
				iCount
			)
		)

	def tag_read(self, req: dict) -> Response:
		"""Tag read

		Finds the tag by name, then returns all related info

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# Init errors
		lErrors = []

		# If the locale or tag is missing is missing
		try: evaluate(req['data'], [ 'locale', 'tag' ])
		except ValueError as e:
			lErrors.extend([ [ s, 'missing' ] for s in e.args ])

		# If the page is missing
		if 'page' not in req['data']:
			iPage = 1

		# Else, we got a page
		else:

			# Try to convert it
			try:
				iPage = int(req['data']['page'])
			except ValueError as e:
				lErrors.append([ 'page', 'invalid' ])

			# If it's less than 1, reject it
			if iPage < 1:
				lErrors.append([ 'page', 'invalid' ])

		# If the count is missing
		if 'count' not in req['data']:
			iCount = 10

		# Else, we got a count
		else:

			# Try to convert it
			try: iCount = int(req['data']['count'])
			except ValueError as e:
				lErrors.append([ 'count', 'invalid' ])

			# If it's less than 1, reject it
			if iPage < 1:
				lErrors.append([ 'count', 'invalid' ])

		# If there's any errors
		if lErrors:
			return Error(errors.DATA_FIELDS, lErrors)

		# Fetch and return the posts
		return Response(
			PostTag.locale_cache_fetch(
				req['data']['tag'],
				req['data']['locale'],
				iPage - 1,
				iCount
			)
		)

	def tags_read(self, req: dict) -> Response:
		"""Tags read

		Returns all the current tags by a specific locale

		Arguments:
			req (dict): The request details, which can include 'data', \
				'environment', and 'session'

		Returns:
			Services.Response
		"""

		# If the locale is missing
		if 'locale' not in req['data']:
			return Error(errors.DATA_FIELDS, [ [ 'locale', 'missing' ] ])

		# Fetch and return the tags by locale
		return Response(
			PostTag.all_locale_cache_fetch(req['data']['locale'])
		)