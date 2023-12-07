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
	PostLocale.table_create()
	PostLocaleTag.table_create()

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
	def filter(cls, options: dict, custom: dict = {}) -> List[dict]:
		"""Filter

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

		# Select and return the data
		return Record_MySQL.Commands.select(
			dStruct['host'],
			sSQL,
			Record_MySQL.ESelect.ALL
		)

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
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""

		# Return the config
		return cls._conf

class PostLocale(Record_MySQL.Record):
	"""Post Locale

	Represents the text data for a specific locale associated with a post. \
	i.e. translation data for a single locale

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post_locale.json' % _defPath),
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

class PostLocaleTag(Record_MySQL.Record):
	"""Post Locale Tag

	Represents a tag and the post translation it's associated with

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record_MySQL.Record.generate_config(
		Tree.fromFile('%s/post_locale_tag.json' % _defPath),
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