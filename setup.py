#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name = 'peertools',
    version = '0.4',
    description = 'Router Peering Management Tools',
    author = 'RIPE NCC',
    author_email = 'dbayer@ripe.net',
    url = 'https://github.com/RIPE-NCC/peertools',
    packages = find_packages(),
    zip_safe = False,
    package_data = {
        '': [ 'static/*.*', 'static/images/*.*' ]
    },
    install_requires = [
        'netaddr',
        'prettytable',
        'sqlalchemy',
        'cherrypy',
        'pymysql',
        'pexpect',
        'argparse',
    ],
    scripts = [
        'bin/peercli',
        'bin/peerweb',
        'bin/peerdbcli',
    ],
)
