# coding=utf8
""" Install

Method to install the necessary blog tables
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__version__		= "1.0.0"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-27"

# Ouroboros imports
from config import config
from rest_mysql import Record_MySQL
from upgrade import set_latest

# Python imports
from os.path import abspath, expanduser
from pathlib import Path

# Module imports
from blog.records import category, category_locale, comment, media, post,\
	post_category, post_raw, post_tag

def run() -> int:
	"""Run

	Entry point into the install process. Will install required files, tables, \
	records, etc. for the service

	Returns:
		int
	"""

	# Add the global prepend
	Record_MySQL.db_prepend(config.mysql.prepend(''))

	# Add the primary mysql DB
	Record_MySQL.add_host(
		'blog',
		config.mysql.hosts[config.blog.mysql('primary')]({
			'host': 'localhost',
			'port': 3306,
			'charset': 'utf8mb4',
			'user': 'root',
			'passwd': ''
		})
	)

	# Notify
	print('Installing tables')

	# Install tables
	category.Category.table_create()
	category_locale.CategoryLocale.table_create()
	comment.Comment.table_create()
	media.Media.table_create()
	post.Post.table_create()
	post_category.PostCategory.table_create()
	post_raw.PostRaw.table_create()
	post_tag.PostTag.table_create()

	# Notify
	print('Setting lastest version')

	# Get the path to the data folder
	sData = config.blog.data('./.data')
	if '~' in sData:
		sData = expanduser(sData)
	sData = abspath(sData)

	# Store the last known upgrade version
	set_latest(
		sData,
		Path(__file__).parent.resolve()
	)

	# Notify
	print('Done')

	# Return OK
	return 0