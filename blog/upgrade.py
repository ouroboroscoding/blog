# coding=utf8
""" Upgrade

Method to upgrade the necessary blog tables
"""

__author__		= "Chris Nasr"
__copyright__	= "Ouroboros Coding Inc."
__version__		= "1.0.0"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2025-11-18"

# Ouroboros imports
from config import config
from upgrade_oc import upgrade as oc_upgrade

# Python imports
from os.path import abspath, expanduser
from pathlib import Path

def run() -> int:
	"""Run

	Entry point into the upgrade process. Will upgrades required files, \
	tables, records, etc. for the service

	Returns:
		int
	"""

	# Get the path to the data folder
	sData = config.blog.data('./.data')
	if '~' in sData:
		sData = expanduser(sData)
	sData = abspath(sData)

	# Run the upgrade scripts avaialble and store the new version number
	return oc_upgrade(
		data_path = sData,
		module_path = Path(__file__).parent.resolve(),
		mode = 'module'
	)