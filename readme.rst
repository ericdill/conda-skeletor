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

So, what does ``conda-skeletor`` do?  Executing `conda-skeletor path-to-codebase` will:

#. Parse your (Python!) codebase and find all imports
#. Split those imports based on if they are:

  - **builtins** (using `stdlib-list <https://github.com/jackmaney/python-stdlib-list>`_)
  - **relative imports** (just in case you're curious?)
  - **questionable imports** if they are wrapped in a try/except block (That, I
    cannot determine how to handle without input from you)
  - **required imports** if they are at the top level of your module
  - **optional imports** if they are found inside a function

#. Create a meta.yaml file based on this information (plus a little bit of
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

- valid keys to meta.tmpl:

``package:``

- **packagename** the name of the package. Can be obtained from setup.py
- **packageversion** the version string of the package. If not provided then
  git describe will be used to determine the tag ::

  - v0.1.0
  - {{ environ['GIT_DESCRIBE_TAG'] }}.post{{ environ['GIT_DESCRIBE_NUMBER'] }}

``source:``

- **git** bool; whether the source code is under git version control
- **source_url** the source for the conda-recipe. Defaults to setup.py 'url'
- **source_rev** the version of the source. Defaults to master. Used if
  source_url is not '../'

``build:``

- **build_number** defaults to 0
- **build_string** The build string for the build artifact ::

    - Should be empty if we are building off of a tag
    - Should be string: ``{{ environ.get('GIT_BUILD_STR', '') }}_np{{ np }}py{{ py }}``
      if ``numpy`` is a build dependency
    - Should be ``string: {{ environ.get('GIT_BUILD_STR', '') }}_py{{ py }}``
      if ``numpy`` is not a build dependency

- **entry_points** Console scripts that can be parsed from setup.py if any exist

``requirements:``

- **python_version_build** string. The python version required for building ``>=3.4``, ``<=2.7``, etc
- **python_version_run** string.  The python version required for running ``>=3.4``, ``<=2.7``, etc
- **build_dep** list. The list of build time dependencies
- **run_dep** list. The list of run time dependencies

``test:``

- **import_deps** list. The list of imports required to successfully execute
  the test(s)
- **import_modules** list. The list of modules to import in the test suite to
  test to make sure that the package was correctly built
- **test_commands** list. The list of test scripts to be executed

``about:``
- **home_url** string. The url that is considered the home page for the project.
  can be obtained from setup.py
- **license** string. The license under which the project is released. Can be
  obtained from setup.py