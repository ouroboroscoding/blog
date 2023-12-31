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
from tools import without

# Python imports
import os
import pathlib
from typing import List

# Pip imports
from FormatOC import Tree
from RestOC import Record_MySQL

# Get the definitions path
_defPath = '%s/definitions' % pathlib.Path(__file__).parent.resolve()

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
			dResults[sSlugLocale].categories.append(d['_category'])

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
			dResults[sSlugLocale].tags.append(d['tag'])

		# Return the results
		return dResults

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

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

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf