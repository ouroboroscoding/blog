# coding=utf8
""" Blog Category Records

Handles the individual category records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'Category' ]

# Ouroboros imports
from config import config
from define import Tree
from rest_mysql.Record_MySQL import Record

# Python imports
import pathlib

# Record imports
from blog.records import records

class Category(Record):
	"""Category

	Represents a category in the system

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/category.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': True,
				'changes': [ 'user' ],
				'create': [ '_created' ],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': { },
				'table': 'blog_category',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_bin'
			},

			'_id': { '__sql__': { 'binary': True } },
			'_created': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP'
			} }
		})
	)
	"""Configuration"""

	@classmethod
	def config(cls):
		"""Config

		Returns the configuration data associated with the record type

		Returns:
			dict
		"""
		return cls._conf

# Add the class instance
records.Category = Category