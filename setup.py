from setuptools import setup

with open('README.md', 'r') as oF:
	long_description=oF.read()

setup(
	name='blog-oc',
	version='0.1.2',
	description='Blog contains a service to manage blog posts and comments associated',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://ouroboroscoding.com/body/blog',
	project_urls={
		'Documentation': 'https://ouroboroscoding.com/body/blog',
		'Source': 'https://github.com/ouroboroscoding/blog',
		'Tracker': 'https://github.com/ouroboroscoding/blog/issues'
	},
	keywords=['rest','microservices'],
	author='Chris Nasr - Ouroboros Coding Inc.',
	author_email='chris@ouroboroscoding.com',
	license='Custom',
	packages=['blog'],
	package_data={'blog': [
		'definitions/*.json',
		'media/*',
		'translations/*.json',
		'upgrades/*'
	]},
	python_requires='>=3.10',
	install_requires=[
		'body-oc>=1.0.2,<1.1',
		'brain-oc>=1.1.9,<1.2',
		'config-oc>=1.0.3,<1.1',
		'jsonb>=1.0.0,<1.1',
		'namedredis>=1.0.1,<1.1',
		'rest-oc>=1.3.0,<1.4',
		'strings-oc>=1.0.5,<1.1',
		'tools-oc>=1.2.4,<1.3',
		'undefined-oc>=1.0.0,<1.1',
		'upgrade-oc>=1.0.2,<1.1'
	],
	entry_points={
		'console_scripts': ['blog=blog.__main__:cli']
	},
	zip_safe=True
)