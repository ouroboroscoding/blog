# coding=utf8
""" Blog Post Category Records

Handles the individual post category records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'PostCategory' ]

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

class PostCategory(Record):
	"""Post Category

	Represents a post category in the system

	Extends:
		Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/post_category.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': False,
				'create': [ '_slug', '_category' ],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'ui_slug_category': { 'unique': [ '_slug', '_category' ] }
				},
				'primary': False,
				'table': 'blog_post_category',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_bin'
			},

			'_slug': { '__sql__': { 'type': 'varchar(128)' } },
			'_category': { '__sql__': { 'binary': True } }
		})
	)
	"""Configuration"""

	_category_key = 'blog:cat:%s'
	"""Key used to store / fetch the cache of slugs by category / locale"""

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
	def cache_fetch(cls,
		slug: str,
		page: int = 0,
		count: int = 10,
		custom = { }
	) -> List[str]:
		"""Cache Fetch

		Fetches the slugs of posts associated with the category

		Arguments:
			slug (str): The category to fetch the list of post slugs for
			page (uint): The page (starting with zero) to fetch of slugs
			count (uint): The count of slugs to return
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			str[]
		"""

		# Fetch the slugs from the cache
		sCategory = records.redis.get(cls._category_key % slug)

		# If it doesn't exist
		if not sCategory:

			# Generate and return it
			dCategory = cls.cache_generate(slug, custom)
			if dCategory is None:
				return None

		# If we got -1, return None
		elif sCategory == '-1' or sCategory == b'-1':
			return None

		# Else, decode them
		else:
			dCategory = jsonb.decode(sCategory)

		# Add the total count
		dCategory['count'] = len(dCategory['posts'])

		# Pull out the IDs specifically for the given page/count
		iStart = page * count
		iEnd = iStart + count
		dCategory['posts'] = dCategory['posts'][iStart:iEnd]

		# Get the individual posts and add them to the return
		dCategory['posts'] = records.c.Post.cache_fetch(dCategory['posts'])

		# Return the posts and total count
		return dCategory

	@classmethod
	def cache_generate(cls,
		slug: str,
		custom = {}
	) -> List[str]:
		"""Cache Generate

		Takes a category and generates the list of slugs available in that \
		category and locale, then stores it in the cache for future use

		Arguments:
			slug (str): The category slug to generate the list of post slugs for
			custom (dict): Custom Host and DB info
				'host' the name of the host to get/set data on
				'append' optional postfix for dynamic DBs

		Returns:
			dict
		"""

		# Get the structures
		dStruct = cls.struct(custom)
		dCategory = records.c.CategoryLocale.struct(custom)
		dPost = records.c.Post.struct(custom)

		# Generate the SQL to fetch all the slugs that fit the category and the
		#	locale
		sSQL = "SELECT `p`.`_slug`\n" \
				"FROM `%(db)s`.`%(table)s` as `c`\n" \
				"JOIN `%(db_cl)s`.`%(table_cl)s` as `cl`\n" \
				"	ON `c`.`_category` = `cl`.`_category`\n" \
				"JOIN `%(db_p)s`.`%(table_p)s` as `p`\n" \
				"	ON `c`.`_slug` = `p`.`_slug`\n" \
				"WHERE `cl`.`slug` = %(slug)s\n" \
				"AND `cl`.`_locale` = `p`.`_locale`\n" \
				"ORDER BY `p`.`_created` DESC" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'db_cl': dCategory['db'],
			'table_cl': dCategory['table'],
			'db_p': dPost['db'],
			'table_p': dPost['table'],
			'slug': cls.escape(dCategory, 'slug', slug)
		}

		# Fetch the column of slugs
		lSlugs = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.COLUMN
		)

		# If there's nothing under that category
		if not lSlugs:

			# Mark it as not existing for an hour so that no one can overload
			#	the DB
			records.redis.set(
				cls._category_key % slug,
				'-1',
				ex = 3600
			)

			# Then immediately return as there's nothing else to do
			return None

		# Fetch the category info
		dCategory = records.c.CategoryLocale.filter({
			'slug': slug
		}, raw = ['_category', '_locale', 'title', 'description' ], limit = 1)

		# Add the post slugs to it
		dCategory['posts'] = lSlugs

		# Permanently store the data in the cache
		records.redis.set(
			cls._category_key % slug,
			jsonb.encode(dCategory)
		)

		# Return the category in case anyone needs it
		return dCategory

# Add the class instance
records.c.PostCategory = PostCategory