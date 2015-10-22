import setuptools
from setuptools import setup
VERSION = 'v0.0.1'
setup(
    name='conda_skeletor',
    version=VERSION,
    author='Eric Dill',
    author_email='thedizzle@gmail.com',
    description='Automagically generate conda recipes from your source',
    url='http://github.com/ericdill/conda-skeletor',
    platforms='Cross platform (Linux, Mac OSX, Windows)',
    license="BSD",
    packages=setuptools.find_packages(),
    package_data={'conda_skeletor.templates': ['*'],
                  'conda_skeletor': ['*.yml']},
    include_package_data=True,
    install_requires=['setuptools', 'pyyaml', 'jinja2', 'depfinder'],
    entry_points={
        'console_scripts': [
            'conda-skeletor = conda_skeletor.main:main',
        ],
    },
)
