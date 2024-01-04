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
from body import errors
from config import config

# Python imports
from os import environ

# Pip imports
from RestOC import EMail, REST, Services, Session

# Module imports
from .service import Blog

def run():
	"""Run

	Starts the http REST server
	"""

	# Init the email module
	EMail.init(config.email({
		'error_to': 'errors@localhost',
		'from': 'admin@localhost',
		'smtp': {
			'host': 'localhost',
			'port': 587,
			'tls': True,
			'user': 'noone',
			'passwd': 'nopasswd'
		}
	}))

	# Get redis session config
	dRedis = config.redis.session({
		'host': 'localhost',
		'port': 6379,
		'db': 0,
		'charset': 'utf8'
	})

	# Init the Session module
	Session.init(dRedis)

	# Get the REST config
	dRest = config.rest({
		'allowed': 'localhost',
		'default': {
			'domain': 'localhost',
			'host': '0.0.0.0',
			'port': 8800,
			'protocol': 'http',
			'workers': 1
		},
		'services': {
			'brain': {'port': 0},
			'blog': {'port': 2}
		}
	})

	# Create the REST config instance
	oRestConf = REST.Config(dRest)

	# Set verbose mode if requested
	if 'VERBOSE' in environ and environ['VERBOSE'] == '1':
		Services.verbose()

	# Get all the services
	dServices = { k:None for k in dRest['services'] }

	# Add this service
	dServices['blog'] = Blog()

	# Register all services
	Services.register(
		dServices,
		oRestConf,
		config.services.salt(),
		config.services.internal_key_timeout(10)
	)

	# Create the HTTP server and map requests to service
	REST.Server({

		'/admin/category': { 'methods': REST.CREATE | REST.DELETE | REST.READ },
		'/admin/category/locale': { 'methods': REST.CREATE | REST.DELETE | REST.UPDATE },

		'/admin/post': { 'methods': REST.ALL },
		'/admin/post/publish': { 'methods': REST.UPDATE },
		'/admin/post/unpublished': { 'methods': REST.READ },
		'/admin/posts': { 'methods': REST.READ },

		'/admin/media': { 'methods': REST.CREATE | REST.DELETE | REST.READ },
		'/admin/media/filter': { 'methods': REST.READ },
		'/admin/media/thumbnail': { 'methods': REST.CREATE | REST.DELETE },
		'/admin/media/url': { 'methods': REST.READ },

		'/category': { 'methods': REST.READ },
		'/post': { 'methods': REST.READ },
		'/tag': { 'methods': REST.READ }

		},
		'blog',
		'https?://(.*\\.)?%s' % config.rest.allowed('localhost').replace('.', '\\.'),
		error_callback = errors.service_error
	).run(
		host=oRestConf['blog']['host'],
		port=oRestConf['blog']['port'],
		workers=oRestConf['blog']['workers'],
		timeout='timeout' in oRestConf['blog'] and oRestConf['blog']['timeout'] or 30
	)