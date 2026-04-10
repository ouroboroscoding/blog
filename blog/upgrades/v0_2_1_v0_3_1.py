# coding=utf8
""" Upgrade 0.2.1 to 0.3.0

Handles taking the existing 0.2.1 data and converting it to a usable format in
0.3.0
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__version__		= "1.0.0"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Ouroboros imports
from config import config
import jsonb
from rest_mysql.Record_MySQL import Commands, DuplicateException, ESelect
from strings import uuid_strip_dashes

# Python imports
from os import makedirs
from os.path import abspath, expanduser, exists

# Pip imports
from pymysql.converters import escape_string

# Local imports
from blog.records import category, category_locale, comment, media, post, \
	post_category, post_raw

def run():
	"""Run

	Main entry into the script, called by the upgrade module

	Returns:
		bool
	"""

	# Get Mouth data folder
	sDataPath = config.blog.data('./.data')
	if '~' in sDataPath:
		sDataPath = expanduser(sDataPath)
	sDataPath = abspath(sDataPath)

	# If the path doesn't exist
	if not exists(sDataPath):
		makedirs(sDataPath)

	############################################################################
	# Category section

	# Get the categorys struct
	dStruct = category.Category.struct()

	# Generate the name of the category changes backup file
	sCategoryChangesFile = '%s/blog_v0_3_category_changes.json' % sDataPath

	# If the backup file already exists
	if exists(sCategoryChangesFile):

		# Load it
		lChangeRecords = jsonb.load(sCategoryChangesFile)

	# Else, no backups yet
	else:

		# Pull out all the records from the category changes table
		lChangeRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, UNIX_TIMESTAMP(`created`) as `created`, `items` ' \
			'FROM `%(db)s`.`%(table)s_changes` ORDER BY `created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lChangeRecords, sCategoryChangesFile)

	# Generate the name of the categorys backup file
	sCategorysFile = '%s/blog_v0_3_categorys.json' % sDataPath

	# If the backup file already exists
	if exists(sCategorysFile):

		# Load it
		lRecords = jsonb.load(sCategorysFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the category table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sCategorysFile)

		# Drop the table
		category.Category.table_drop()

		# Recreate the table
		category.Category.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_id'] = uuid_strip_dashes(d['_id'])
			category.Category.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	# Go through each changes record, convert the values, and add them
	for d in lChangeRecords:
		dStruct['_id'] = uuid_strip_dashes(d['_id'])
		dStruct['created'] = d['created']
		dStruct['items'] = escape_string(d['items'])
		sSQL = "INSERT INTO `%(db)s`.`%(table)s_changes` " \
					"(`_id`, `created`, `items`) " \
				"VALUES (UNHEX('%(_id)s'), FROM_UNIXTIME(%(created)s), " \
					"'%(items)s')" % dStruct
		Commands.execute(dStruct['host'], sSQL)

	############################################################################
	# Category Locale section

	# Get the category_locales struct
	dStruct = category_locale.CategoryLocale.struct()

	# Generate the name of the template email changes backup file
	sLocaleChangesFile = '%s/blog_v0_3_category_locale_changes.json' % sDataPath

	# If the backup file already exists
	if exists(sLocaleChangesFile):

		# Load it
		lChangeRecords = jsonb.load(sLocaleChangesFile)

	# Else, no backups yet
	else:

		# Pull out all the records from the template email changes table
		lChangeRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, UNIX_TIMESTAMP(`created`) as `created`, `items` ' \
			'FROM `%(db)s`.`%(table)s_changes` ORDER BY `created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lChangeRecords, sLocaleChangesFile)

	# Generate the name of the category_locales backup file
	sLocalesFile = '%s/blog_v0_3_category_locales.json' % sDataPath

	# If the backup file already exists
	if exists(sLocalesFile):

		# Load it
		lRecords = jsonb.load(sLocalesFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the template email table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created`, ' \
				'`_category`, `_locale`, `slug`, `title`, `description` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sLocalesFile)

		# Drop the table
		category_locale.CategoryLocale.table_drop()

		# Recreate the table
		category_locale.CategoryLocale.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_id'] = uuid_strip_dashes(d['_id'])
			d['_category'] = uuid_strip_dashes(d['_category'])
			category_locale.CategoryLocale.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	# Go through each changes record, convert the values, and add them
	for d in lChangeRecords:
		dStruct['_id'] = uuid_strip_dashes(d['_id'])
		dStruct['created'] = d['created']
		dStruct['items'] = escape_string(d['items'])
		sSQL = "INSERT INTO `%(db)s`.`%(table)s_changes` " \
					"(`_id`, `created`, `items`) " \
				"VALUES (UNHEX('%(_id)s'), FROM_UNIXTIME(%(created)s), " \
					"'%(items)s')" % dStruct
		Commands.execute(dStruct['host'], sSQL)

	############################################################################
	# Comment section

	# Get the template_sms struct
	dStruct = comment.Comment.struct()

	# Generate the name of the comment backup file
	sCommentFile = '%s/blog_v0_3_comment.json' % sDataPath

	# If the backup file already exists
	if exists(sCommentFile):

		# Load it
		lRecords = jsonb.load(sCommentFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the template sms table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created`, ' \
				'`_post`, `_locale`, `_ip`, `_approved`, `_comment`, ' \
				'`name`, `content` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sCommentFile)

		# Drop the table
		comment.Comment.table_drop()

		# Recreate the table
		comment.Comment.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_id'] = uuid_strip_dashes(d['_id'])
			d['_post'] = uuid_strip_dashes(d['_post'])
			if d['_comment']:
				d['_comment'] = uuid_strip_dashes(d['_comment'])
			comment.Comment.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	############################################################################
	# Media section

	# Get the medias struct
	dStruct = media.Media.struct()

	# Generate the name of the medias backup file
	sMediaFile = '%s/blog_v0_3_medias.json' % sDataPath

	# If the backup file already exists
	if exists(sMediaFile):

		# Load it
		lRecords = jsonb.load(sMediaFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the template email table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created`, ' \
				'`uploader`, `filename`, `mime`, `length`, `image` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sMediaFile)

		# Drop the table
		media.Media.table_drop()

		# Recreate the table
		media.Media.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_id'] = uuid_strip_dashes(d['_id'])
			d['uploader'] = uuid_strip_dashes(d['uploader'])
			d['image'] = jsonb.decode(d['image'])
			media.Media.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	############################################################################
	# Post section

	# Get the posts struct
	dStruct = post.Post.struct()

	# Generate the name of the posts backup file
	sPostsFile = '%s/blog_v0_3_posts.json' % sDataPath

	# If the backup file already exists
	if exists(sPostsFile):

		# Load it
		lRecords = jsonb.load(sPostsFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the post table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_slug`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created`, ' \
				'UNIX_TIMESTAMP(`_updated`) as `_updated`, ' \
				'`_raw`, `_locale`, `title`, `content`, ' \
				'`meta`, `locales` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sPostsFile)

		# Drop the table
		post.Post.table_drop()

		# Recreate the table
		post.Post.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_raw'] = uuid_strip_dashes(d['_raw'])
			d['meta'] = jsonb.decode(d['meta'])
			d['locales'] = jsonb.decode(d['locales'])
			post.Post.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	############################################################################
	# Post Category section

	# Get the post_categorys struct
	dStruct = post_category.PostCategory.struct()

	# Generate the name of the post_categorys backup file
	sPostCategorysFile = '%s/blog_v0_3_post_categorys.json' % sDataPath

	# If the backup file already exists
	if exists(sPostCategorysFile):

		# Load it
		lRecords = jsonb.load(sPostCategorysFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the post_category table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_slug`, `_category` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_slug`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sPostCategorysFile)

		# Drop the table
		post_category.PostCategory.table_drop()

		# Recreate the table
		post_category.PostCategory.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_category'] = uuid_strip_dashes(d['_category'])
			post_category.PostCategory.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	############################################################################
	# Post Raw section

	# Get the post_raws struct
	dStruct = post_raw.PostRaw.struct()

	# Generate the name of the template email changes backup file
	sPostRawChangesFile = '%s/blog_v0_3_post_raw_changes.json' % sDataPath

	# If the backup file already exists
	if exists(sPostRawChangesFile):

		# Load it
		lChangeRecords = jsonb.load(sPostRawChangesFile)

	# Else, no backups yet
	else:

		# Pull out all the records from the template email changes table
		lChangeRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, UNIX_TIMESTAMP(`created`) as `created`, `items` ' \
			'FROM `%(db)s`.`%(table)s_changes` ORDER BY `created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lChangeRecords, sPostRawChangesFile)

	# Generate the name of the post_raws backup file
	sPostRawFile = '%s/blog_v0_3_post_raws.json' % sDataPath

	# If the backup file already exists
	if exists(sPostRawFile):

		# Load it
		lRecords = jsonb.load(sPostRawFile)

	# Else, no backup yet
	else:

		# Pull out all the records from the template email table
		lRecords = Commands.select(
			dStruct['host'],
			'SELECT `_id`, ' \
				'UNIX_TIMESTAMP(`_created`) as `_created`, ' \
				'UNIX_TIMESTAMP(`_updated`) as `_updated`, ' \
				'UNIX_TIMESTAMP(`last_published`) as `last_published`, ' \
				'`categories`, `locales` ' \
			'FROM `%(db)s`.`%(table)s` ORDER BY `_created`' % dStruct,
			ESelect.ALL
		)

		# Store them to a local file
		jsonb.store(lRecords, sPostRawFile)

		# Drop the table
		post_raw.PostRaw.table_drop()

		# Recreate the table
		post_raw.PostRaw.table_create()

	# Go through each record, convert the values, and add them
	for d in lRecords:
		try:
			d['_id'] = uuid_strip_dashes(d['_id'])
			d['categories'] = jsonb.decode(d['categories'])
			for i, s in enumerate(d['categories']):
				d['categories'][i] = uuid_strip_dashes(s)
			d['locales'] = jsonb.decode(d['locales'])
			post_raw.PostRaw.create_now(d, changes = False)
		except DuplicateException as e:
			print(e.args)

	# Go through each changes record, convert the values, and add them
	for d in lChangeRecords:
		dStruct['_id'] = uuid_strip_dashes(d['_id'])
		dStruct['created'] = d['created']
		dStruct['items'] = escape_string(d['items'])
		sSQL = "INSERT INTO `%(db)s`.`%(table)s_changes` " \
					"(`_id`, `created`, `items`) " \
				"VALUES (UNHEX('%(_id)s'), FROM_UNIXTIME(%(created)s), " \
					"'%(items)s')" % dStruct
		Commands.execute(dStruct['host'], sSQL)

	# Return OK
	return True