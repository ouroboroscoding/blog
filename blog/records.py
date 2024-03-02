# coding=utf8
""" Records

Handles the record structures for the blog service
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-27"

# Ouroboros imports
from config import config
import jsonb

# Python imports
import os
import pathlib
from typing import List

# Pip imports
from FormatOC import Tree
from RestOC import Record_MySQL

# Module variable
_moRedis = None

# Get the definitions path
_defPath = '%s/definitions' % pathlib.Path(__file__).parent.resolve()

def cache(redis=None):
	"""Cache

	Get/Set the cache instance

	Arguments:
		redis (StrictRedis): The instance to set, None for getting

	Returns:
		None|StrictRedis
	"""
	global _moRedis
	if not redis:
		return _moRedis
	else:
		_moRedis = redis

def install():
	"""Install

	Handles the initial creation of the tables in the DB

	Returns:
		None
	"""
	Category.table_create()
	CategoryLocale.table_create()
	Comment.table_create()
	Media.table_create()
	Post.table_create()
	PostCategory.table_create()
	PostRaw.table_create()
	PostTag.table_create()

class Category(Record_MySQL.Record):
	"""Category

	Represents a category for blog posts to be in

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/category.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

class CategoryLocale(Record_MySQL.Record):
	"""Category Locale

	Represents the text data for a specific locale associated with a category. \
	i.e. translation data for a single locale

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/category_locale.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

class Comment(Record_MySQL.Record):
	"""Comment

	Represents a single comment associated with a post

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/comment.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

class Media(Record_MySQL.Record):
	"""Media

	Represents a category for blog posts to be in

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/media.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

	@classmethod
	def _filename(self, data: dict, size: str = 'source') -> str:
		"""Filename (static)

		Generate the filename based on the size given

		Arguments:
			file (dict): Media record data
			size (str): Optional, the size of the file, defaults to 'source' \
				to fetch the original unaltered file

		Returns:
			str
		"""

		# Split the filename
		lFile = os.path.splitext(data['filename'])

		# Return the generated string
		return '%s/%s%s%s' % (
			data['_id'],
			lFile[0],
			(size == 'source' and '' or ('_%s' % size)),
			lFile[1]
		)

	def filename(self, size: str = 'source') -> str:
		"""Filename

		Generate the filename based on the size given

		Arguments:
			size (str): Optional, the size of the file, defaults to 'source' \
				to fetch the original unaltered file

		Returns:
			str
		"""
		return self._filename(self._dRecord, size)

	@classmethod
	def search(cls, options: dict, custom: dict = {}) -> List[dict]:
		"""Search

		Fetches media files based on options

		Arguments:
			options (dict): Options: range: list, filename: str, mine: bool
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict[]
		"""

		# Get the structure
		dStruct = cls.struct(custom)

		# Create the WHERE clauses
		lWhere = []
		if 'range' in options:
			lWhere.append('`_created` BETWEEN FROM_UNIXTIME(%d) AND ' \
				 			'FROM_UNIXTIME(%d)' % (
				options['range'][0], options['range'][1]
			))
		if 'filename' in options and options['filename']:
			lWhere.append("`filename` LIKE '%%%s%%'" % \
				Record_MySQL.Commands.escape(
					dStruct['host'], options['filename']
				)
			)
		if 'mine' in options and options['mine']:
			lWhere.append("`uploader` = '%s'" % options['mine'])
		if 'images_only' in options:
			lWhere.append('`image` IS NOT NULL')

		# If we have nothing
		if not lWhere:
			return []

		# Generate the SQL
		sSQL = "SELECT *\n" \
			 	"FROM `%(db)s`.`%(table)s`\n" \
				"WHERE %(where)s" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'where': ' AND '.join(lWhere)
		}

		# Fetch the records
		lRecords = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# Go through each record
		for d in lRecords:

			# If we have image data
			if 'image' in d and d['image']:
				d['image'] = jsonb.decode(d['image'])

		# Return the records
		return lRecords

class Post(Record_MySQL.Record):
	"""Post

	Represents a single blog post

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	_post_key = 'blog:post:%s'
	"""Key used to store / fetch the cache of a specific post by slug"""

	_posts_key = 'blog:posts:%s'
	"""Key used to store / fetch the cache of all posts by locale"""

	@classmethod
	def by_category(cls, locale, category, custom = {}):
		"""By Category

		Fetches all the post titles and slugs associated with a category in a \
		specific locale

		Arguments:
			locale (str): The locale to use to fetch the posts
			category (str): The ID of the category to fetch for

		Returns:
			list
		"""

		# Get the structure
		dStruct = cls.struct(custom)

		# Generate the SQL to get the titles and slugs
		sSQL = "SELECT `p`.`_created`," \
			 	" `p`.`_updated`," \
				" `p`.`_slug`," \
				" `p`.`title`\n" \
				"FROM `%(db)s`.`%(table)s` as `p`\n" \
				"JOIN `%(db)s`.`%(table)s_category` as `pc` ON" \
				" `p`.`_slug` = `pc`.`_slug`\n" \
				"WHERE `pc`.`_category` = '%(cat)s'\n" \
				"AND `p`.`_locale` = '%(locale)s'" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'cat': Record_MySQL.Commands.escape(dStruct['host'], category),
			'locale': Record_MySQL.Commands.escape(dStruct['host'], locale),
		}

		# Fetch and return the results
		return Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

	@classmethod
	def by_raw(cls, _id, custom = {}):
		"""By Raw

		Fetches all posts, their categories, and their tags by the posts raw ID

		Arguments:
			_id (str): The ID of the PostRaw record
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict of slugs+locale to dict of post / categories / tags
		"""

		# Init the results
		dResults = {}

		# Get the structure
		dStruct = cls.struct(custom)

		# Escape the ID
		sID = Record_MySQL.Commands.escape(dStruct['host'], _id)

		# Generate the SQL to fetch the posts
		sSQL = "SELECT * FROM `%(db)s`.`%(table)s`\n" \
				"WHERE `_raw` = '%(id)s'" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'id': sID
		}

		# Fetch the records
		lRecords = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# Go through each one and store it by slug and locale
		for d in lRecords:

			# Generate the unique string
			sSlugLocale = '%s:%s' % (d['_slug'], d['_locale'])

			# Convert the json values
			d['meta'] = jsonb.decode(d['meta'])
			d['locales'] = jsonb.decode(d['locales'])

			# Add empty category and tag lists
			d['categories'] = []
			d['tags'] = []

			# Add it to the results
			dResults[sSlugLocale] = d

		# Generate the SQL to fetch the categories
		sSQL = "SELECT `p`.`_slug`, `p`.`_locale`, `pc`.`_category`\n" \
				"FROM `%(db)s`.`%(table)s` as `p`\n" \
				"JOIN `%(db)s`.`%(table)s_category` as `pc` ON" \
				" `p`.`_slug` = `pc`.`_slug`\n" \
				"WHERE `p`.`_raw` = '%(id)s'" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'id': sID
		}

		# Fetch the records
		lRecords = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# Go through each one
		for d in lRecords:

			# Generate the unique string
			sSlugLocale = '%s:%s' % (d['_slug'], d['_locale'])

			# Add the category to the post
			dResults[sSlugLocale]['categories'].append(d['_category'])

		# Generate the SQL to fetch the tags
		sSQL = "SELECT `p`.`_slug`, `p`.`_locale`, `pt`.`tag`\n" \
				"FROM `%(db)s`.`%(table)s` as `p`\n" \
				"JOIN `%(db)s`.`%(table)s_tag` as `pt` ON" \
				" `p`.`_slug` = `pt`.`_slug`\n" \
				"WHERE `p`.`_raw` = '%(id)s'" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'id': sID
		}

		# Fetch the records
		lRecords = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# Go through each one
		for d in lRecords:

			# Generate the unique string
			sSlugLocale = '%s:%s' % (d['_slug'], d['_locale'])

			# Add the category to the post
			dResults[sSlugLocale]['tags'].append(d['tag'])

		# Return the results
		return dResults

	@classmethod
	def cache_delete(cls, slug: str) -> bool:
		"""Cache Delete

		Deletes a post from the cache

		Arguments:
			slug (str): The slug of the post

		Returns:
			None
		"""

		# Delete it
		_moRedis.get(cls._post_key % slug)

	@classmethod
	def cache_fetch(cls, slug: str | List[str], custom = {}) -> dict:
		"""Cache Fetch

		Fetches the post from the cache, if it doesn't exist, it's generated \
		first

		Arguments:
			slug (str | str[]): The slug(s) of the post(s) to fetch
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Return:
			dict
		"""

		# If we got a single slug
		if isinstance(slug, str):

			# Fetch it from the cache
			sPost = _moRedis.get(cls._post_key % slug)

			# If it doesn't exist
			if not sPost:

				# Generate and return it
				return cls.cache_generate(slug, custom)

			# If we got -1, return None
			if sPost == '-1' or sPost == b'-1':
				return None

			# Decode and return the post
			return jsonb.decode(sPost)

		# Fetch all the posts by slug
		lPosts = _moRedis.mget([ cls._post_key % s for s in slug ])

		# Go through each one
		for i in range(len(lPosts)):

			# If it's missing
			if not lPosts[i]:

				# Try to find it by the slug
				lPosts[i] = cls.cache_generate(slug[i])

			# Else, if it's -1
			elif lPosts[i] == '-1' or lPosts[i] == b'-1':

				# Set it to None
				lPosts[i] = None

			# Else
			else:

				# Decode it
				lPosts[i] = jsonb.decode(lPosts[i])

		# Return the posts
		return lPosts

	@classmethod
	def cache_generate(cls, slug: str, custom = {}) -> dict:
		"""Cache Generate

		Generates and stores the cache record for a single post by slug, then \
		returns the post in case it's needed

		Arguments:
			slug (str): The slug of the post to generate and store
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Return:
			dict
		"""

		# Fetch the post by slug
		dPost = Post.get(
			slug,
			raw = [
				'_slug', '_locale', '_created', '_updated', 'title', 'content',
				'meta', 'locales'
			]
		)

		# If it doesn't exist
		if not dPost:

			# Mark it as not existing for an hour so that no one can overload
			#	the DB
			_moRedis.set(
				cls._post_key % slug,
				'-1',
				ex = 3600
			)

			# Then immediately return as there's nothing else to do
			return None

		# Find all the associated categories and add them to the post
		dPost['categories'] = [ d['_category'] for d in PostCategory.filter({
			'_slug': slug
		}, raw = [ '_category' ]) ]

		# Find all the associated tags and add them to the post
		dPost['tags'] = [ d['tag'] for d in PostTag.filter({
			'_slug': slug
		}, raw = [ 'tag' ]) ]

		# Store the record permanently in the cache
		_moRedis.set(cls._post_key % slug, jsonb.encode(dPost))

		# Return the post
		return dPost

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

	@classmethod
	def locale_cache_fetch(cls,
		locale: str,
		page: int = 0,
		count: int = 10,
		custom: dict = {}
	):
		"""Locale Cache Fetch

		Fetches all posts in a specific locale for a specific page. If the \
		cache doesn't exist, it is generated and stored first, then the \
		specific is returned

		Arguments:
			locale (str): The locale to fetch the tags for
			page (uint): The page (starting with zero) to fetch of slugs
			count (uint): The count of slugs to return
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict[]
		"""

		# Fetch the post IDs
		sSlugs = _moRedis.get(cls._posts_key % locale)

		# If it doesn't exist
		if not sSlugs:

			# Generate the list
			lSlugs = cls.locale_cache_generate(locale, custom)

		# Else, we got tags back
		else:

			# Decode them
			lSlugs = jsonb.decode(sSlugs)

		# Init the result with the total count
		dReturn = { 'count': len(lSlugs) }

		# Pull out the IDs specifically for the given page/count
		iStart = page * count
		iEnd = iStart + count
		lSlugs = lSlugs[iStart:iEnd]

		# Get the individual posts and add them to the return
		dReturn['posts'] = cls.cache_fetch(lSlugs)

		# Return the posts and total count
		return dReturn

	@classmethod
	def locale_cache_generate(cls, locale: str, custom: dict = {}):
		"""Locale Cache Generate

		Takes a locale and generates the list of tags available in that locale \
		based on the posts in that locale, then stores it in the cache for \
		future use

		Arguments:
			locale (str): The locale to generate the tags for
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict[]
		"""

		# Get the structs
		dStruct = cls.struct(custom)

		# Create the SQL to fetch all slugs associated with posts in a specific
		#	locale
		sSQL = "SELECT `_slug`\n" \
				"FROM `%(db)s`.`%(table)s`\n" \
				"WHERE `_locale` = '%(locale)s'\n" \
				"ORDER BY `_created` DESC" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'locale': Record_MySQL.Commands.escape(dStruct['host'], locale)
		}

		# Fetch the slugs
		lSlugs = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.COLUMN
		)

		# Store the slugs in the cache
		_moRedis.set(
			cls._posts_key % locale,
			jsonb.encode(lSlugs)
		)

		# Return the slugs in case someone needs them
		return lSlugs

class PostCategory(Record_MySQL.Record):
	"""Post Category

	Represents an association between a blog post and a category

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post_category.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

class PostRaw(Record_MySQL.Record):
	"""Post Raw

	Represents the raw data with all locales, categories, and tags used to \
	make posts

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post_raw.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

	def localesToSlugs(self, ignore):
		"""Locales to Slugs

		Returns a dict of locales to their slugs, not including the ignored \
		locale if it's passed

		Arguments:
			ignore (str): Locale to not include in the dict

		Returns:
			dict of locales to slugs
		"""

		# Create a list of the locales, skipping the one we are ignoring, and
		#	sort them alphabetically
		lLocales = sorted([ k for k in self['locales'] if k != ignore ])

		# Create the dict using the locales and the slugs in each, then return
		#	it
		return { k : self['locales'][k]['slug'] for k in lLocales }

	@classmethod
	def unpublished(cls, custom = {}):
		"""Unpublished

		Returns raw blog posts that haven't been published, or that have \
		unpublished changes

		Arguments:
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			list
		"""

		# Get the structure
		dStruct = cls.struct(custom)

		# Generate the SQL
		sSQL = "SELECT * FROM `%(db)s`.`%(table)s`\n" \
				"WHERE `last_published` IS NULL\n" \
				"OR `_updated` > `last_published`\n" \
				"ORDER BY `_updated`" % {
			'db': dStruct['db'],
			'table': dStruct['table']
		}

		# Fetch the records
		lRecords = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# If there's no records, return
		if not lRecords:
			return []

		# Go through each record
		for d in lRecords:

			# If we have categories, decode them
			if 'categories' in d:
				d['categories'] = jsonb.decode(d['categories'])

			# Decode the locales
			d['locales'] = jsonb.decode(d['locales'])

		# Return the records
		return lRecords

class PostTag(Record_MySQL.Record):
	"""Post Tag

	Represents a tag and the post it's associated with

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post_tag.json' % _defPath),
		override={ 'db': config.mysql.db('brain') }
	)
	"""Static Configuration"""

	_tag_key = 'blog:tag:%s:%s'
	"""Key used to store / fetch the cache of slugs by tag / locale"""

	_tags_key = 'blog:tags:%s'
	"""Key used to store / fetch the cache of all tags by locale"""

	@classmethod
	def all_locale_cache_fetch(cls,
		locale: str,
		custom: dict = {}
	) -> List[dict]:
		"""Tags Locale Cache Fetch

		Fetches all tags in a specific locale. If the cache doesn't exist, it \
		is generated and stored first, then returned

		Arguments:
			locale (str): The locale to fetch the tags for
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict[]
		"""

		# Fetch the tags
		lTags = _moRedis.get(cls._tags_key % locale)

		# If it doesn't exist
		if not lTags:

			# Generate the list and return it
			return cls.locale_cache_generate(locale, custom)

		# Decode the cache and return
		return jsonb.decode(lTags)

	@classmethod
	def all_locale_cache_generate(cls,
		locale: str,
		custom: dict = {}
	) -> List[dict]:
		"""Tags Locale Cache Generate

		Takes a locale and generates the list of tags available in that locale \
		based on the posts in that locale, then stores it in the cache for \
		future use

		Arguments:
			locale (str): The locale to generate the tags for
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict[]
		"""

		# Get the structs
		dStruct = cls.struct(custom)
		dPost = Post.struct(custom)

		# Create the SQL to fetch all tags associated with posts in a specific
		#	locale
		sSQL = "SELECT `t`.`tag`, COUNT(*) as `count`\n" \
				"FROM `%(db)s`.`%(table)s` as `t`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	 ON `t`.`_slug` = `p`.`_slug`\n" \
				"WHERE `p`.`_locale` = '%(locale)s'\n" \
				"GROUP BY `t`.`tag`\n" \
				"ORDER BY `t`.`tag`" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'locale': Record_MySQL.Commands.escape(dStruct['host'], locale)
		}

		# Fetch the tags
		lTags = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

		# Store the tags in the cache
		_moRedis.set(
			cls._tags_key % locale,
			jsonb.encode(lTags)
		)

		# Return the tags in case someone needs them
		return lTags

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

	@classmethod
	def locale_cache_fetch(cls,
		tag: str,
		locale: str,
		page: int = 0,
		count: int = 10,
		custom = {}
	) -> List[str]:
		"""Locale Cache Fetch

		Fetches the slugs of posts associated with the tag and locale

		Arguments:
			tag (str): The tag to generate the list of slugs for
			locale (str): The locale to fetch posts from
			page (uint): The page (starting with zero) to fetch of slugs
			count (uint): The count of slugs to return
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			str[]
		"""

		# Fetch the slugs from the cache
		sSlugs = _moRedis.get(cls._tag_key % (tag, locale))

		# If it doesn't exist
		if not sSlugs:

			# Generate and return it
			lSlugs = cls.locale_cache_generate(tag, locale, custom)
			if lSlugs is None:
				return None

		# If we got -1, return None
		elif sSlugs == '-1' or sSlugs == b'-1':
			return None

		# Else, decode them
		else:
			lSlugs = jsonb.decode(sSlugs)

		# Init the result with the total count
		dReturn = { 'count': len(lSlugs) }

		# Pull out the IDs specifically for the given page/count
		iStart = page * count
		iEnd = iStart + count
		lSlugs = lSlugs[iStart:iEnd]

		# Get the individual posts and add them to the return
		dReturn['posts'] = Post.cache_fetch(lSlugs)

		# Return the posts and total count
		return dReturn

	@classmethod
	def locale_cache_generate(cls,
		tag: str,
		locale: str,
		custom = {}
	) -> List[str]:
		"""Locale Cache Generate

		Takes a tag and locale and generates the list of slugs available in \
		that locale based on the posts in that locale, then stores it in the \
		cache for future use

		Arguments:
			tag (str): The tag to generate the list of slugs for
			locale (str): The locale to fetch posts from
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			str[]
		"""

		# Get the structures
		dStruct = cls.struct(custom)
		dPost = Post.struct(custom)

		# Generate the SQL to fetch all the slugs that fit the tag and the
		#	locale
		sSQL = "SELECT `p`.`_slug`\n" \
				"FROM `%(db)s`.`%(table)s` as `t`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	ON `t`.`_slug` = `p`.`_slug`\n" \
				"WHERE `t`.`tag` = '%(tag)s'\n" \
				"AND `p`.`_locale` = '%(locale)s'\n" \
				"ORDER BY `p`.`_created` DESC" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'tag': Record_MySQL.Commands.escape(dStruct['host'], tag),
			'locale': Record_MySQL.Commands.escape(dStruct['host'], locale)
		}

		# Fetch the column of slugs
		lSlugs = Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.COLUMN
		)

		# If there's nothing under that tag
		if not lSlugs:

			# Mark it as not existing for an hour so that no one can overload
			#	the DB
			_moRedis.set(
				cls._tag_key % (tag, locale),
				'-1',
				ex = 3600
			)

			# Then immediately return as there's nothing else to do
			return None

		# Permanently store them in the cache
		_moRedis.set(cls._tag_key % (tag, locale), jsonb.encode(lSlugs))

		# Return the slugs in case anyone needs them
		return lSlugs