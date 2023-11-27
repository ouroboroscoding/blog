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
from upgrade import set_latest

# Module imports
from blog import records

def install(conf):
	"""Install

	Installs required files, tables, records, etc. for the service

	Arguments:
		conf (dict): The blog config

	Returns:
		int
	"""

	# Install tables
	records.install()

	# Store the last known upgrade version
	set_latest(conf['data'], conf['module'])

	# Return OK
	return 0