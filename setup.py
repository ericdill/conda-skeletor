from setuptools import setup
VERSION = 'v0.0.1'
setup(name='conda-skeletor',
      version=VERSION,
      author='Eric Dill',
      author_email='thedizzle@gmail.com',
      py_modules=['conda_skeletor'],
      description='Automagically generate conda recipes from your source',
      url='http://github.com/ericdill/conda-skeletor',
      platforms='Cross platform (Linux, Mac OSX, Windows)',
      install_requires=['setuptools'],
)
