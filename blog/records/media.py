# coding=utf8
""" Blog Media Records

Handles the individual media records available on the system
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Limit exports
__all__ = [ 'Media' ]

# Ouroboros imports
from config import config
from define import Tree
import jsonb
from rest_mysql.Record_MySQL import Commands, ESelect, Record

# Python imports
import os
import pathlib
from pymysql.converters import escape_string
from typing import List

# Record imports
from blog import records

class Media(Record):
	"""Media

	Represents a media in the system

	Extends:
		Record_MySQL.Record
	"""

	_conf = Record.generate_config(
		Tree.from_file('%s/define/media.json' % pathlib.Path(
			__file__
		).parent.parent.resolve(), {
			'__name__': 'record',
			'__sql__': {
				'auto_primary': True,
				'create': [
					'_created', 'uploader', 'filename', 'mime', 'length',
					'image'
				],
				'db': config.mysql.db('blog'),
				'host': config.blog.mysql('records'),
				'indexes': {
					'i_created': [ '_created' ],
					'i_uploader': [ 'uploader' ],
					'i_filename': { 'unique': [ 'filename' ] }
				},
				'table': 'blog_media',
				'charset': 'utf8mb4',
				'collate': 'utf8mb4_unicode_ci'
			},

			'_id': { '__sql__': { 'binary': True } },
			'_created': { '__sql__': {
				'opts': 'not null default CURRENT_TIMESTAMP'
			} },
			'uploader': { '__sql__': { 'binary': True } },
			'image': { '__sql__': { 'json': True } }
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

	@classmethod
	def _filename(self, data: dict, size: str = 'source') -> str:
		"""Filename (static)

		Generate the filename based on the size given

		Arguments:
			file (dict): Media record data
			size (str): Optional, the size of the file, defaults to 'source'
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
			size (str): Optional, the size of the file, defaults to 'source'
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
				escape_string(options['filename'])
			)
		if 'mine' in options and options['mine']:
			lWhere.append("`uploader` = '%s'" % options['mine'])
		if 'images_only' in options:
			lWhere.append('`image` IS NOT NULL')

		# If we have nothing
		if not lWhere:
			return []

		# Generate the SQL
		sSQL = "SELECT %(fields)s\n" \
			 	"FROM `%(db)s`.`%(table)s`\n" \
				"WHERE %(where)s" % {
			'db': dStruct['db'],
			'table': dStruct['table'],
			'fields': cls.provide_select(struct = dStruct),
			'where': ' AND '.join(lWhere)
		}

		# Fetch the records
		lRecords = Commands.select(
			dStruct['host'],
			sSQL,
			ESelect.ALL
		)

		# Go through each record
		for d in lRecords:

			# If we have image data
			if 'image' in d and d['image']:
				d['image'] = jsonb.decode(d['image'])

		# Return the records
		return lRecords

# Add the class instance
records.c.Media = Media