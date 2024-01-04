# coding=utf8
""" Blog Media

Provides the base class used to create storage systems for the media
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-30"

# Limit exports
__all__ = [ 'Storage' ]

# Python imports
import abc

class BaseMediaStorage(abc.ABC):
	"""Base Media Storage

	The base class for all child media storage classes
	"""

	_last_error: str | None = None
	"""Last Error

	User to store the last error(s) related to any call"""

	@abc.abstractmethod
	def delete(self, filename: str) -> bool:
		"""Delete

		Deletes the file by filename

		Arguments:
			filename (str): The name of the file to delete

		Returns:
			bool
		"""
		pass

	def last_error(self) -> str:
		"""Last Error

		Returns the last error associated with the last failed method call

		Returns:
			str
		"""
		return self._last_error

	@abc.abstractmethod
	def open(self, filename: str) -> bytes:
		"""Open

		Fetches a file's raw bytes and returns them

		Arguments:
			filename (str): The name of the file to open

		Returns:
			bytes
		"""
		pass

	@abc.abstractmethod
	def save(self, filename: str, content: bytes) -> bool:
		"""Save

		Saves a files raw bytes by filename

		Arguments:
			filename (str): The name of the file to save
			content (bytes): The bytes to save under the filename

		Returns:
			bool
		"""
		pass

	@abc.abstractmethod
	def url(self, filename: str) -> str:
		"""URL

		Returns a URL capable of loading the file

		Arguments:
			filename (str): The name of the file to generate a URL for

		Returns:
			str
		"""
		pass