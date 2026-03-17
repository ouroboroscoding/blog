# coding=utf8
""" Blog Post Tag Records

Handles the individual post tag records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'PostTag' ]

# Ouroboros imports
from config import config
from define import Tree
import jsonb
from rest_mysql.Record_MySQL import Commands, ESelect, Record

# Python imports
import pathlib
from typing import Dict, List

# Record imports
from blog import records

class PostTag(Record):
	"""Post Tag

	Represents a post tag in the system

	Extends:
		Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/post_tag.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': False,
				'create': [ '_slug', 'tag' ],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'i_slug_name': { 'unique': [ '_slug', 'tag' ] }
				},
				'primary': False,
				'table': 'blog_post_tag',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_bin'
			},

			'_slug': { '__sql__': {  'type': 'varchar(128)' } },
			'tag': { '__sql__': { 'type': 'varchar(32)' } }
		})
	)
	"""Configuration"""

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
		lTags = records.redis.get(cls._tags_key % locale)

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
		dPost = records.c.Post.struct(custom)

		# Create the SQL to fetch all tags associated with posts in a specific
		#	locale
		sSQL = "SELECT `t`.`tag`, COUNT(*) as `count`\n" \
				"FROM `%(db)s`.`%(table)s` as `t`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	 ON `t`.`_slug` = `p`.`_slug`\n" \
				"WHERE `p`.`_locale` = %(locale)s\n" \
				"GROUP BY `t`.`tag`\n" \
				"ORDER BY `t`.`tag`" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'locale': cls.escape(dPost, '_locale', locale)
		}

		# Fetch the tags
		lTags = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
		)

		# Store the tags in the cache
		records.redis.set(
			cls._tags_key % locale,
			jsonb.encode(lTags)
		)

		# Return the tags in case someone needs them
		return lTags

	@classmethod
	def by_slugs(cls, slugs: List[str], custom = {}) -> Dict[str, List[str]]:
		"""By Post

		Fetches the tags and locales associated with a single post

		Arguments:
			slugs (str[]): The slugs to fetch tags for
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict
		"""

		# Get the structs
		dStruct = cls.struct(custom)
		dPost = records.c.Post.struct(custom)

		# Generate SQL to fetch all tags and their locales associated with the
		#	given post
		sSQL = "SELECT `t`.`tag`, `p`.`_locale`\n" \
				"FROM `%(db)s`.`%(table)s` as `t`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	ON `t`.`_slug` = `p`.`_slug`\n" \
				"WHERE `p`.`_slug` %(slugs)s\n" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'slugs': cls.process_value(dStruct, '_slug', slugs)
		}

		# Get the records
		lRows = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
		)

		# Go through each one and store the tags by locale
		dTags = {}
		for d in lRows:
			try: dTags[d['_locale']].append(d['tag'])
			except: dTags[d['_locale']] = [ d['tag'] ]

		# Return the tags by locale
		return dTags

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
		sSlugs = records.redis.get(cls._tag_key % (tag, locale))

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
		dReturn['posts'] = records.c.Post.cache_fetch(lSlugs)

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
		dPost = records.c.Post.struct(custom)

		# Generate the SQL to fetch all the slugs that fit the tag and the
		#	locale
		sSQL = "SELECT `p`.`_slug`\n" \
				"FROM `%(db)s`.`%(table)s` as `t`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	ON `t`.`_slug` = `p`.`_slug`\n" \
				"WHERE `t`.`tag` = %(tag)s\n" \
				"AND `p`.`_locale` = %(locale)s\n" \
				"ORDER BY `p`.`_created` DESC" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'tag': cls.escape(dStruct, 'tag', tag),
			'locale': cls.escape(dPost, '_locale', locale)
		}

		# Fetch the column of slugs
		lSlugs = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.COLUMN
		)

		# If there's nothing under that tag
		if not lSlugs:

			# Mark it as not existing for an hour so that no one can overload
			#	the DB
			records.redis.set(
				cls._tag_key % (tag, locale),
				'-1',
				ex = 3600
			)

			# Then immediately return as there's nothing else to do
			return None

		# Permanently store them in the cache
		records.redis.set(cls._tag_key % (tag, locale), jsonb.encode(lSlugs))

		# Return the slugs in case anyone needs them
		return lSlugs

# Store the record
records.c.PostTag = PostTag