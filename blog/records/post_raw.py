# coding=utf8
""" Blog Post Raw Records

Handles the individual post raw records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'PostRaw' ]

# Ouroboros imports
from config import config
from define import Tree
import jsonb
from rest_mysql.Record_MySQL import Commands, ESelect, Record

# Python imports
import pathlib

# Record imports
from blog.records import records

class PostRaw(Record):
	"""Post Raw

	Represents a post raw in the system

	Extends:
		Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/post_raw.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': True,
				'changes': [ 'user' ],
				'create': [
					'_created', '_updated', 'last_published', 'categories',
					'locales'
				],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'i_created': [ '_created' ],
					'i_updated': [ '_updated' ],
					'i_last_published': [ 'last_published' ]
				},
				'table': 'blog_post_raw',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_bin'
			},

			'_id': { '__sql__': { 'binary': True } },
			'_created': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP'
			} },
			'_updated': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP ' \
					'on update CURRENT_TIMESTAMP'
			} },
			'categories': { '__sql__': { 'json': True } },
			'locales': { '__sql__': { 'json': True } }
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
		sSQL = "SELECT %(fields)s\n" \
				"FROM `%(db)s`.`%(table)s`\n" \
				"WHERE `last_published` IS NULL\n" \
				"OR `_updated` > `last_published`\n" \
				"ORDER BY `_updated`" % {
			'fields': cls.provide_select(),
			'db': dStruct['db'],
			'table': dStruct['table']
		}

		# Fetch the records
		lRecords = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
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

# Add the class instance
records.PostRaw = PostRaw