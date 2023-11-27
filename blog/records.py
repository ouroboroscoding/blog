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
import pathlib

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