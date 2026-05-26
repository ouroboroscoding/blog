# coding=utf8
""" Upgrade 0.3.0 to 0.3.1

Handles taking the existing 0.3.0 data and converting it to a usable format in
0.3.1
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__version__		= "1.0.0"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Ouroboros imports
import jsonb
from rest_mysql.Record_MySQL import Commands

# Local imports
from blog.records import media

def run():
	"""Run

	Main entry into the script, called by the upgrade module

	Returns:
		bool
	"""

	# Get the media structure
	dS = media.Media.struct()

	# Get the select
	sFields = media.Media.provide_select(
		[ '_id', 'image' ],
		struct = dS
	)

	# Fetch all the media records
	lRecords = Commands.select(
		dS['host'],
		f"SELECT {sFields} FROM `{dS['db']}`.`{dS['table']}`"
	)

	# Go through each record
	for d in lRecords:

		# Convert the string to a string
		d['image'] = jsonb.decode(d['image'])

		# Update the record
		Commands.execute(dS['host'], (
			f"UPDATE `{dS['db']}`.`{dS['table']}` "
			f"SET `image` = '{d['image']}' "
			f"WHERE `_id` = UNHEX('{d['_id']}')"
		))

	# Return OK
	return True