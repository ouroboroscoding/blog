# coding=utf8
""" Records

Handles shared records connections
"""

__author__		= "Chris Nasr"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Ouroboros modues
import jobject

c = jobject()
"""Holds the instances of each record type"""

redis = None
"""Redis records connection"""