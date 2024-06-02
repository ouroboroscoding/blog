# coding=utf8
""" Blog Sitemap

Returns the list of posts and categories in the system for the purposes of a \
sitemap
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__copyright__	= "Ouroboros Coding Inc."
__email__		= "chris@ouroboroscoding.com"
__created__		= "2024-05-27"

# Ouroboros imports
import config
import undefined
from RestOC import Record_MySQL

# Python imports
from typing import List, Tuple
from urllib.parse import quote_plus

# Pip imports
import arrow

# Project records
from blog.records import CategoryLocale, Post, PostTag

# Constants
DEFAULT_FREQUENCY = 'always'
DEFAULT_PRIORITY = '0.5'

def pages(
	url_root: str = '/blog/',
	url_post: str = 'p/',
	url_category: str = 'c/',
	url_tag: str = 't/',
	priorities: dict | str = undefined,
	frequencies: dict | str = undefined
) -> List[Tuple]:
	"""Pages

	Returns the list of pages in the blog system. Must provide the root and \
	prefixes for the page types. Optionally, individual priorities and \
	frequencies can be set per type, or globally:

	Set each priority: { 'post': '1.0', 'category': '0.9', 'tag': '0.8' }
	Set one priority and a default: { 'post': '1.0', 'default': '0.5' }
	Set a single default: { 'default': '1.0' }

	Types are the same across both, 'post', 'category', and 'tag'.

	If priorities are not passed at all, all pages are set to '0.5' by \
	default. If frequencies are not at all, all pages are set to 'always' by \
	default.

	Arguments:
		url_root (str): The root of all URLS
		url_post (str): The post folder prefix
		url_category (str): The category folder prefix
		url_tag (str): The tag folder prefix
		priorities (dict): The priorities to give page types

	Returns:
		tuple[]
	"""

	# If priorities is not set
	if priorities is undefined:
		dPriorities = { 'default': DEFAULT_PRIORITY }

	# If it's a dict
	elif isinstance(priorities, dict):
		dPriorities = priorities

	# Else, if it's a string
	elif isinstance(priorities, str):
		dPriorities = { 'default': priorities }

	# Else, it's invalid
	else:
		raise TypeError(
			'blog.sitemap.pages.priorities',
			'must be a dict or str'
		)

	# If there's no default
	if 'default' not in dPriorities:
		dPriorities['default'] = DEFAULT_PRIORITY

	# If frequencies is not set
	if frequencies is undefined:
		dFrequencies = { 'default': DEFAULT_FREQUENCY }

	# If it's a dict
	elif isinstance(frequencies, dict):
		dFrequencies = frequencies

	# Else, if it's a string
	elif isinstance(frequencies, str):
		dFrequencies = { 'default': frequencies }

	# Else, it's invalid
	else:
		raise TypeError(
			'blog.sitemap.pages.frequencies',
			'must be a dict or str'
		)

	# If there's no default
	if 'default' not in dFrequencies:
		dFrequencies['default'] = DEFAULT_FREQUENCY

	# Add the global prepend
	Record_MySQL.db_prepend(config.mysql.prepend(''))

	# Add the primary mysql DB
	Record_MySQL.add_host(
		'blog',
		config.mysql.hosts[config.blog.mysql_host('blog')]({
			'host': 'localhost',
			'port': 3306,
			'charset': 'utf8',
			'user': 'root',
			'passwd': ''
		})
	)

	# Set the timestamp timezone
	Record_MySQL.timestamp_timezone(
		config.mysql.timestamp_timezone('+00:00')
	)

	# Init the return list
	lPages = []

	# Fetch the slug of all the posts
	lPosts = Post.get(raw = [ '_slug', '_updated' ])

	# Go through each post
	for d in lPosts:

		# Page priority
		sPriority = 'post' in dPriorities and \
			dPriorities['post'] or \
			dPriorities['default']

		# Page change frequency
		sFrequency = 'post' in dFrequencies and \
			dFrequencies['post'] or \
			dFrequencies['default']

		# Add the page to the list
		lPages.append((
			'%s%s%s' % (
				url_root,
				url_post,
				d['_slug']
			),
			arrow.get(d['_updated']).isoformat(),
			sFrequency,
			sPriority
		))

	# Get the slug of all categories
	lCategories = CategoryLocale.get(raw = [ 'slug' ])

	# Go through each category
	for d in lCategories:

		# Page priority
		sPriority = 'category' in dPriorities and \
			dPriorities['category'] or \
			dPriorities['default']

		# Page change frequency
		sFrequency = 'category' in dFrequencies and \
			dFrequencies['category'] or \
			dFrequencies['default']

		# Add the category to the list
		lPages.append((
			'%s%s%s' % (
				url_root,
				url_category,
				d['slug']
			),
			arrow.get().isoformat(),
			sFrequency,
			sPriority
		))

	# Get all the tags
	lTags = PostTag.get(distinct = True, raw = [ 'tag' ])

	# Go through each tag
	for d in lTags:

		# Page priority
		sPriority = 'tag' in dPriorities and \
			dPriorities['tag'] or \
			dPriorities['default']

		# Page change frequency
		sFrequency = 'tag' in dFrequencies and \
			dFrequencies['tag'] or \
			dFrequencies['default']

		# Add the tag to the list
		lPages.append((
			'%s%s%s' % (
				url_root,
				url_tag,
				quote_plus(d['tag'])
			),
			arrow.get().isoformat(),
			sFrequency,
			sPriority
		))

	# Return the list
	return lPages