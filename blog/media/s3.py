# coding=utf8
""" Blog Media S3

Handles storing and fetching media files from Amazon's S3 service
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-30"

# Limit exports
__all__ = [ 'MediaStorage' ]

# Ouroboros modules
from config import config

# Python modules
from time import sleep

# Import pip modules
import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from botocore.vendored.requests.packages.urllib3.exceptions import \
	ReadTimeoutError

# Local modules
from . import BaseMediaStorage

class __S3Storage(BaseMediaStorage):
	"""S3 Storage

	Handles storing and fetching media files from S3

	Extends:
		BaseMediaStorage
	"""

	def __init__(self) -> None:
		"""Constructor

		Instantiates the instance

		Returns:
			__S3Storage
		"""

		# Fetch the config
		dConf = config.blog.s3({
			'bucket': 'development',
			'settings': {
				'connect_timeout': 5,
				'read_timeout': 2
			},
			'max_timeouts': 5,
			'path': '',
			'profile': 's3'
		})

		# Store the bucket, path, and max timeout values
		self._bucket = dConf['bucket']
		self._max_timeouts = int(dConf['max_timeouts'])
		self._path = dConf['path']

		# Create a new session using the profile given
		self._session = boto3.Session(profile_name = dConf['profile'])

		# Get an S3 resource using the session
		self._resource = self._session.resource(
			's3', config = BotoConfig(**dConf['settings'])
		)

		# Get a client using the session
		self._client = self._session.client(
			's3',
			config = boto3.session.Config(
				s3 = { 'addressing_style': 'path' },
				signature_version = 's3v4'
			)
		)

	def delete(self, filename: str) -> bool:
		"""Delete

		Deletes the file by filename

		Arguments:
			filename (str): The name of the file to delete

		Returns:
			bool
		"""

		# Init the key using the filename
		sKey = filename

		# If there's a path, prepend it
		if self._path:
			sKey = self._path + sKey

		# Keep trying if we get timeout errors
		iTimeouts = 0
		while True:

			try:

				# Attempt to delete the object
				return self._resource.Object(self._bucket, sKey).delete()

			# If there's a client issue, i.e. the bucket, credentials, etc are
			#	invalid
			except ClientError as e:

				# Store the error message
				self._last_error = [
					'S3 client error', e.args, self._bucket, sKey
				]

				# Return failure
				return False

			# If S3 is not responding
			except ReadTimeoutError as e:

				# Increment the timeout counter
				iTimeouts += 1

				# If we're reached the maximum
				if iTimeouts >= self._max_timeouts:

					# Store the error message
					self._last_error = [
						'S3 max timeouts', e.args, self._bucket, sKey
					]

					# Return failure
					return False

				# We still have attempts, sleep and loop back around
				sleep(1)
				continue

			# If we get any other exception
			except Exception as e:

				# Store the error message
				self._last_error = [
					'S3 unknown exception', e.args, self._bucket, sKey
				]

				# Return failure
				return False

	def open(self, filename: str) -> bytes | None:
		"""Open

		Fetches a file's raw bytes and returns them

		Arguments:
			filename (str): The name of the file to open

		Returns:
			bytes | None
		"""

		# Init the key using the filename
		sKey = filename

		# If there's a path, prepend it
		if self._path:
			sKey = self._path + sKey

		# Keep trying if we get timeout errors
		iTimeouts = 0
		while True:

			try:

				# Attempt to fetch the object
				dBlob = self._resource.Object(self._bucket, sKey).get()

				# Return the body
				return dBlob['Body'].read()


			# If there's a client issue, i.e. the bucket, credentials, etc are
			#	invalid
			except ClientError as e:

				# Store the error message
				self._last_error = [
					'S3 client error', e.args, self._bucket, sKey
				]

				# Return failure
				return None

			# If S3 is not responding
			except ReadTimeoutError as e:

				# Increment the timeout counter
				iTimeouts += 1

				# If we're reached the maximum
				if iTimeouts >= self._max_timeouts:

					# Store the error message
					self._last_error = [
						'S3 max timeouts', e.args, self._bucket, sKey
					]

					# Return failure
					return None

				# We still have attempts, sleep and loop back around
				sleep(1)
				continue

			# If we get any other exception
			except Exception as e:

				# Store the error message
				self._last_error = [
					'S3 unknown exception', e.args, self._bucket, sKey
				]

				# Return failure
				return None

	def save(self, filename: str, content: bytes, mime: str = None) -> bool:
		"""Save

		Saves a files raw bytes by filename

		Arguments:
			filename (str): The name of the file to save
			content (bytes): The bytes to save under the filename
			mime (str): Optional, the mime type of the file

		Returns:
			bool
		"""

		# Init the headers with the acl, body, and length
		dHeaders = {
			'ACL': 'public-read',
			'Body': content,
			'ContentLength': len(content)
		}

		# If we have the mime type
		if mime is not None:
			dHeaders['ContentType'] = mime

		# Init the key using the filename
		sKey = filename

		print('save:')
		print(sKey)

		# If there's a path, prepend it
		if self._path:
			print('has path')
			sKey = self._path + sKey
		print(sKey)

		# Keep trying if we get timeout errors
		iTimeouts = 0
		while True:

			# Create new object and upload it
			try:
				return self._resource.Object(
					self._bucket, sKey
				).put(**dHeaders)

			# If there's a client issue, i.e. the bucket, credentials, etc are
			#	invalid
			except ClientError as e:

				# Store the error message
				self._last_error = [
					'S3 client error', e.args, self._bucket, sKey
				]

				# Return failure
				return False

			# If S3 is not responding
			except ReadTimeoutError as e:

				# Increment the timeout counter
				iTimeouts += 1

				# If we're reached the maximum
				if iTimeouts >= self._max_timeouts:

					# Store the error message
					self._last_error = [
						'S3 max timeouts', e.args, self._bucket, sKey
					]

					# Return failure
					return False

				# We still have attempts, sleep and loop back around
				sleep(1)
				continue

			# If we get any other exception
			except Exception as e:

				# Store the error message
				self._last_error = [
					'S3 unknown exception', e.args, self._bucket, sKey
				]

				# Return failure
				return False

	def url(self, filename: str) -> str:
		"""URL

		Returns a URL capable of loading the file

		Arguments:
			filename (str): The name of the file to generate a URL for

		Returns:
			str
		"""

		# Init the key using the filename
		sKey = filename

		# If there's a path, prepend it
		if self._path:
			sKey = self._path + sKey

		# Return the URL
		return 'https://%s.s3.amazonaws.com/%s' % (
			self._bucket,
			sKey
		)

# Create the single instance
MediaStorage = __S3Storage()