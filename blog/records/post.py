# coding=utf8
""" Blog Post Records

Handles the individual post records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'Post' ]

# Ouroboros imports
from config import config
from define import Tree
import jsonb
from rest_mysql.Record_MySQL import Commands, ESelect, Record

# Python imports
import pathlib
from typing import List

# local imports
from blog import records
from blog.records.category_locale import CategoryLocale
from blog.records.post_category import PostCategory
from blog.records.post_tag import PostTag

class Post(Record):
	"""Post

	Represents a post in the system

	Extends:
		Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/post.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': True,
				'create': [
					'_slug', '_raw', '_locale', '_created', '_updated', 'title',
					'content', 'meta', 'locales'
				],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'i_raw': [ '_raw' ],
					'i_locale': [ '_locale' ]
				},
				'primary': '_slug',
				'table': 'blog_post',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_unicode_ci'
			},

			'_slug': { '__sql__': { 'type': 'varchar(128)' } },
			'_raw': { '__sql__': { 'binary': True } },
			'_locale': { '__sql__': { 'type': 'char(5)' } },
			'_created': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP'
			} },
			'_updated': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP ' \
					'on update CURRENT_TIMESTAMP'
			} },
			'content': { '__sql__': { 'type': 'text' } },
			'meta': { '__sql__': { 'json': True } },
			'locale': { '__sql__': { 'json': True } }
		})
	)
	"""Configuration"""

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
			'cat': Commands.escape(dStruct['host'], category),
			'locale': Commands.escape(dStruct['host'], locale),
		}

		# Fetch and return the results
		return Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
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
		sID = Commands.escape(dStruct['host'], _id)

		# Generate the SQL to fetch the posts
		sSQL = "SELECT * FROM `%(db)s`.`%(table)s`\n" \
				"WHERE `_raw` = '%(id)s'" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'id': sID
		}

		# Fetch the records
		lRecords = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
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

		print('-' * 40)
		print(sSQL)

		# Fetch the records
		lRecords = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
		)

		print('-' * 40)
		print(lRecords)

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
		lRecords = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
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
	def cache_delete(cls, slug: str | List[str]) -> bool:
		"""Cache Delete

		Deletes a post from the cache

		Arguments:
			slug (str | str[]): The slug of the post

		Returns:
			None
		"""

		# If we only got one
		if isinstance(slug, str):

			# Delete it
			records.redis.delete(cls._post_key % slug)

		# Else, if we got a list
		elif isinstance(slug, list):

			# Delete them all
			records.redis.delete(*[ cls._post_key % s for s in slug ])

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
			sPost = records.redis.get(cls._post_key % slug)

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
		lPosts = records.redis.mget([ cls._post_key % s for s in slug ])

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
			records.redis.set(
				cls._post_key % slug,
				'-1',
				ex = 3600
			)

			# Then immediately return as there's nothing else to do
			return None

		# Find all the associated categories and add them to the post
		lCategoryIDs = [
			d['_category'] for d in PostCategory.filter({
				'_slug': slug
			}, raw = [ '_category' ])
		]

		# If we have no categories
		if not lCategoryIDs:
			dPost['categories'] = []

		# Else,
		else:

			# Find the category slugs and titles for the categories associated
			#	in the same locale as the post
			dPost['categories'] = CategoryLocale.filter({
				'_category': lCategoryIDs,
				'_locale': dPost['_locale']
			}, raw = [ '_category', 'slug', 'title' ], orderby = [ 'title' ])

		# Find all the associated tags and add them to the post
		dPost['tags'] = [ d['tag'] for d in PostTag.filter({
			'_slug': slug
		}, raw = [ 'tag' ]) ]

		# Store the record permanently in the cache
		records.redis.set(cls._post_key % slug, jsonb.encode(dPost))

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
		sSlugs = records.redis.get(cls._posts_key % locale)

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
			'locale': Commands.escape(dStruct['host'], locale)
		}

		# Fetch the slugs
		lSlugs = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.COLUMN
		)

		# Store the slugs in the cache
		records.redis.set(
			cls._posts_key % locale,
			jsonb.encode(lSlugs)
		)

		# Return the slugs in case someone needs them
		return lSlugs