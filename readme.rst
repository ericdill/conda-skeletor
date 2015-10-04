.. image:: https://travis-ci.org/ericdill/conda-skeletor.svg?branch=master
    :target: https://travis-ci.org/ericdill/conda-skeletor
.. image:: http://codecov.io/github/ericdill/conda-skeletor/coverage.svg?branch=master
    :target: http://codecov.io/github/ericdill/conda-skeletor?branch=master


conda-skeletor
--------------
Manually tweaking conda-recipes make me sad. Much like this:

.. image:: https://pbs.twimg.com/profile_images/448811826873380864/st7dOH-k.jpeg

Who else is sick of hand-curating your conda recipes?  We all know that if you
have the source code then you, a priori, know **all** imports that your library
can ever make.  Granted there are edge cases that are required to keep libraries
compatible with multiple versions of other libraries

- PySide/PyQt4/PyQt5
- py2/py3

This (at least for now) does not solve **that** particular problem (at least
automagically).

So, what does ``conda-skeletor`` do?  `conda-skeletor path-to-codebase` will

1. use `depfinder <https://github.com/ericdill/depfinder>`_ to
  1. Parse your (Python!) codebase and find all imports
  1. Split those imports based on if they are:
    - **builtins** (using `stdlib-list <https://github.com/jackmaney/python-stdlib-list>`_)
    - **relative imports** (just in case you're curious?)
    - **questionable imports** if they are wrapped in a try/except block (That, I
      cannot determine how to handle without input from you)
    - **required imports** if they are at the top level of your module
    - **optional imports** if they are found inside a function
1. Create a meta.yaml file based on this information (plus a little bit of
   extra information that you provide via a conda-skeletor.yml file)


Usage
-----

``conda-skeletor`` is not yet on pypi or anaconda. For now, clone it from
github and install it: ::

    git clone git@github.com:ericdill/conda-skeletor
    cd conda-skeletor
    python setup.py install

Then use it! ::

    conda-skeletor conda-skeletor

This will generate a conda-recipe folder inside of the ``conda-skeletor``
directory with a meta.yaml, build.sh and build.bat.

Notes
-----
- Need to scrape ``setup.py`` to see if the kwargs to setup include
  ``include_package_data`` and ``package_data``. If either of those kwargs are
  present then the Unix build scripts need to be basically this:
  ``$PYTHON setup.py install --single-version-externally-managed --root /``. I
  am not sure what the analogous command is on Windows.
