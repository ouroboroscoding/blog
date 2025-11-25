# coding=utf8
""" Blog Comment Records

Handles the individual comment records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'Comment' ]

# Ouroboros imports
from config import config
from define import Tree
from rest_mysql.Record_MySQL import Record

# Python imports
import pathlib

# Record imports
from blog.records import records

class Comment(Record):
	"""Comment

	Represents a comment in the system

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/comment.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': True,
				'create': [
					'_created', '_post', '_locale', '_ip', '_approved',
					'_comment', 'name', 'content'
				],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'i_post_locale': [ '_post', '_locale' ],
					'i_approved': [ '_approved' ]
				},
				'table': 'blog_comment',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_unicode_ci'
			},

			'_id': { '__sql__': { 'binary': True } },
			'_created': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP'
			} },
			'_post': { '__sql__': { 'binary': True } },
			'_locale': { '__sql__': { 'type': 'char(5)' } },
			'_comment': { '__sql__': { 'binary': True } },
			'_approved': { '__sql__': {
				'opts': 'not null default 0'
			} },
			'content': { '__sql__': { 'type': 'varchar(500)' } }
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
records.Comment = Comment