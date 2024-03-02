# coding=utf8
""" Blog REST

Handles starting the REST server using the Blog service
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__copyright__	= "Ouroboros Coding Inc."
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-27"

# Ouroboros imports
from config import config
import jsonb
from nredis import nr
from strings import strip_html
import undefined

# Python imports
import pathlib
import re
from sys import stderr
from typing import Dict

# Project records
from blog.records import Post, PostTag

# Get the translations path
_translationsPath = '%s/translations' % pathlib.Path(__file__).parent.resolve()

# Page regex
_rePage = re.compile('^([^\/]+)(?:\/(\d+)/?)?$')
_reRoot = re.compile('^(?:(\d+)/?)?$')

class BlogSeo(object):
	"""Blog SEO

	Used to fetch the SEO details of specific blog posts / tags

	Extends:
		object
	"""

	_translations = {}

	def __init__(self,
		url_root: str = '/blog/',
		uri_post: str = 'p/',
		uri_category: str = 'c/',
		uri_tag: str = 't/',
		page_count: int | Dict[str, int] = 10,
		title_prefix: str = undefined,
		title_suffix: str = undefined,
	):
		"""Constructor

		Creates the instance and initialises member variables

		Arguments:
			locale (str): The locale to use
			url_root (str): The root of all URLS
			uri_post (str): The post URI prefix
			uri_tag (str): The tag URI prefix
			page_count (int | dict): The number of posts per page for all \
				types, or a dict of { category, post, tag } with an int for \
				each
			title_prefix (str): Optional, the text to put before the title
			title_suffix (str): Optional, the text to put after the title

		Returns:
			BlogSeo
		"""

		# Store the root, post, and tag prefixes
		self._url = {
			'cat_prefix': uri_category,
			'cat_length': len(uri_category),
			'post_prefix': uri_post,
			'post_length': len(uri_post),
			'root_length': len(url_root),
			'tag_prefix': uri_tag,
			'tag_length': len(uri_tag)
		}

		# Store the page count options
		#	If we got an int, apply it to all types
		if isinstance(page_count, int):
			self._counts = {
				'category': page_count,
				'latest': page_count,
				'tag': page_count
			}

		# Else, if we got a dictionary
		elif isinstance(page_count, dict):

			# Verify all types are present
			if 'category' not in page_count or \
				'latest' not in page_count or \
				'tag' not in page_count:
				raise ValueError(
					'page_count must have one each of "category", "latest", ' \
					'and "tag"'
				)

			# Store the counts
			self._counts = page_count

		# Store the title options
		self._title = {
			'p': title_prefix,
			's': title_suffix
		}

		# Init the list of translations
		self._translations = {}

		# Create the redis instance
		self._redis = nr(config.blog.redis_host('blog'))

	def fetch(self, path: str, locale: str = 'en-US') -> dict:
		"""Fetch

		Receives a URL and figures out the appropriate SEO meta values to \
		return

		Arguments:
			path (str): The URL to find SEO data for
			locale (str): Optional, The locale to use to generate the text. \
				Uses en-US by default

		Returns:
			{ title: str, description: str, image: str, url: str } on success
			None on failure

		"""

		# Init the return
		dRet = None

		# Strip off the scheme and domain
		sPath = path[self._url['root_length']:]

		# If we got a post
		if sPath[:self._url['post_length']] == self._url['post_prefix']:

			# Use the slug to fetch the post
			sCache = self._redis.get(
				Post._post_key % sPath[self._url['post_length']:]
			)

			# If we didn't get the post
			if not sCache or sCache == '-1':
				return None

			# Convert the data
			dPost = jsonb.decode(sCache)

			# Init the return
			dRet = {
				'locale': dPost['_locale'],
				'title': 'meta' in dPost and \
							'title' in dPost['meta'] and \
							dPost['meta']['title'] or \
							dPost['title'],
				'description': 'meta' in dPost and \
								'description' in dPost['meta'] and \
								dPost['meta']['description'] or \
								strip_html(dPost['content'])[:160]
			}

			# If we have meta data
			if 'meta' in dPost:

				# If we have a specific image
				if 'image' in dPost['meta']:
					dRet['image'] = dPost['meta']['image']

				# If we have a specific URL
				if 'url' in dPost['meta']:
					dRet['path'] = dPost['meta']['url']

		# Else, if we got a category
		elif sPath[:self._url['cat_length']] == self._url['cat_prefix']:
			print('Not implemented yet', file = stderr)
			return None

		# Else, if we got a tag
		elif sPath[:self._url['tag_length']] == self._url['tag_prefix']:

			# Get the remainder
			sRemainder = sPath[self._url['post_length']:]

			# Check for a page match
			oMatch = _rePage.match(sRemainder)

			# If we got no match
			if not oMatch:
				return None

			# Store the tag and page
			sTag = oMatch.group(1)
			try: iPage = int(oMatch.group(2))
			except TypeError: iPage = 1

			# Init return
			dRet = {}

			# Use the slug to fetch the tag
			sCache = self._redis.get(
				PostTag._tag_key % ( sTag, locale )
			)

			# If we didn't get the tag
			if not sCache or sCache == '-1':
				return None

			# If we have a page
			if iPage > 1:

				# Convert the cache
				lCache = jsonb.decode(sCache)

				# Div mod the total posts by the count to get the pages
				iPages, iRemainder = divmod(len(lCache), self._counts['tag'])
				if iRemainder: iPages += 1

				# If the page is greater than the total, 404
				if iPage > iPages:
					return None

			# If we don't have translations yet
			if locale not in self._translations:

				# Load the file
				self._translations[locale] = jsonb.load(
					'%s/%s.json' % ( _translationsPath, locale )
				)

			# Set the title and description
			dRet['title'] = self._translations[locale]['tag_title'] % sTag
			dRet['description'] = \
				self._translations[locale]['tag_description'] % sTag
			if iPage > 1:
				dRet['title'] += \
					self._translations[locale]['page_suffix'] % iPage
				dRet['description'] += \
					self._translations[locale]['page_suffix'] % iPage

		# Else
		else:

			# Check for a root match
			oMatch = _reRoot.match(sPath)

			# If we didn't get a match
			if not oMatch:
				return None

			# Check for a page
			try: iPage = int(oMatch.group(1))
			except TypeError: iPage = 1

			# Init return
			dRet = {}

			# If we have a page
			if iPage > 1:

				# Fetch the posts
				sCache = self._redis.get(Post._posts_key % locale)

				# Convert the cache
				lCache = jsonb.decode(sCache)

				# Div mod the total posts by the count to get the pages
				iPages, iRemainder = divmod(len(lCache), self._counts['latest'])
				if iRemainder: iPages += 1

				# If the page is greater than the total, 404
				if iPage > iPages:
					return None

			# If we don't have translations yet
			if locale not in self._translations:

				# Load the file
				self._translations[locale] = jsonb.load(
					'%s/%s.json' % ( _translationsPath, locale )
				)

			# Set the title and description
			dRet['title'] = self._translations[locale]['root_title']
			dRet['description'] = self._translations[locale]['root_description']
			if iPage > 1:
				dRet['title'] += \
					self._translations[locale]['page_suffix'] % iPage
				dRet['description'] += \
					self._translations[locale]['page_suffix'] % iPage

		# If we have a return
		if dRet:

			# If we have a title prefix
			if self._title['p'] is not undefined:
				dRet['title'] = self._title['p'] + dRet['title']

			# If we have a title suffix
			if self._title['s'] is not undefined:
				dRet['title'] += self._title['s']

		# Return
		return dRet