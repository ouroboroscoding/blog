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
from .errors import MINIMUM_LOCALE, NOT_AN_IMAGE, POSTS_ASSOCIATED, \
	STORAGE_ISSUE

# Record classes
from .records import Category, CategoryLocale, Comment, Media, Post, \
	PostCategory, PostLocale, PostLocaleTag

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
		lPosts = Post.filter({
			'category': req['data']['_id']
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

		# Check the minimum fields
		try: evaluate(req['data'], ['locale', 'slug', 'content'])
		except ValueError as e:
			return Error(
				errors.DATA_FIELDS, [ [ s, 'missing' ] for s in e.args ]
			)

		# Init the locale data
		dLocale = {
			'content': req['data']['content'],
			'title': req['data']['title']
		}

		# Make sure the slug doesn't already exist
		if PostLocale.exists(req['data']['slug'], 'slug'):
			return Error(errors.DB_DUPLICATE, [ req['data']['slug'], 'slug' ])

		# Set the slug
		dLocale['slug'] = req['data']['slug']

		# Check for the locale
		oResponse = Services.read('mouth', 'locale/exists', { 'data': {
			'_id': req['data']['locale']
		}})

		# If it doesn't exist on mouth
		if not oResponse.data:
			return Error(
				errors.DB_NO_RECORD, [ req['data']['locale'], 'locale' ]
			)

		# Set the locale
		dLocale['_locale'] = req['data']['locale']

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

		# Create the post instance and create the record to get an ID for the
		#	content and categories
		oPost = Post({
			'_creator': req['session']['user']['_id']
		})
		sPostID = oPost.create(changes = { 'user': req['session']['user']['_id'] })

		# If there's any categories sent
		if 'categories' in req['data'] and req['data']['categories']:

			# Add them to the post
			PostCategory.create_many([
				PostCategory({ '_post': sPostID, '_category': s }) \
				for s in req['data']['categories']
			])

		# Create the primary locale
		dLocale['_post'] = oPost['_id']
		oLocale = PostLocale(dLocale)
		sLocaleID = oLocale.create( changes = {
			'user': req['session']['user']['_id']
		})

		# If we have tags
		if 'tags' in req['data'] and req['data']['tags']:

			# Add them to the post locale
			PostLocaleTag.create_many([
				PostLocaleTag({ '_post_locale': sLocaleID, 'name': s }) \
				for s in req['data']['tags']
			])

		# Return the new ID
		return Response(sPostID)

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
		oPost = Post.get(req['data']['_id'])

		# If it doesn't exist
		if not oPost:
			return Error(errors.DB_NO_RECORD, [ req['data']['_id'], 'post' ])

		# Fetch the locales associated
		lLocales = PostLocale.filter({ '_post': oPost['_id'] }, raw = [ '_id' ])

		# Delete all the tags associated
		PostLocaleTag.delete_get([ d['_id'] for d in lLocales ], '_post_locale')

		# Delete the locales
		PostLocale.delete_get([ d['_id'] for d in lLocales ])

		# Delete all the categories associated
		PostCategory.delete_get(oPost['_id'], '_post')

		# Delete the post
		oPost.delete()

