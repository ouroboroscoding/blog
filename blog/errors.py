# coding=utf8
""" Errors

Blog error codes
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__version__		= "1.0.0"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2023-11-28"

__all__ = ['body']

# Ouroboros imports
from body import errors as body

STORAGE_ISSUE = 1400
"""Storage issue"""

NOT_AN_IMAGE = 1401
"""Attempting to manipulate a file that is not an image"""

POSTS_ASSOCIATED = 1402
"""Attempting to delete a category with posts associated"""