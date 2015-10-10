.. image:: https://travis-ci.org/ericdill/conda-skeletor.svg?branch=master
    :target: https://travis-ci.org/ericdill/conda-skeletor
.. image:: http://codecov.io/github/ericdill/conda-skeletor/coverage.svg?branch=master
    :target: http://codecov.io/github/ericdill/conda-skeletor?branch=master
.. image:: https://coveralls.io/repos/ericdill/conda-skeletor/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/ericdill/conda-skeletor?branch=master

conda-skeletor
--------------
`conda-skeletor` takes the pain out of managing conda-recipes for rapidly
changing repositories. You simply tell it where you source is, how to find
your tests, what to ignore and a few other minor details. It will then parse
your python modules for all Python libraries that are imported and generate a
build script and a meta.yaml from which you can build a conda package!

Motivation
----------
Why is this library called `conda-skeletor`?  Well it's better than the
built-in `conda-skeleton` because `conda-skeletor` will generate a fully
functional meta.yaml for you, not just a skeleton.  How much better than
`conda-skeleton` is `conda-skeletor`? ::

    charsum = lambda s: sum([ord(c) for c in s])
    print(charsum('conda-skeletor') - charsum('conda-skeleton'))

**4**. Yes, that's right. `conda-skeletor` is **4** better than
`conda-skeleton`. Four times better? No. Just four. Four better.

Manually tweaking conda-recipes make me sad. Much like this:

.. image:: https://pbs.twimg.com/profile_images/448811826873380864/st7dOH-k.jpeg

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

- **test_requires** list. The list of imports required to successfully execute
  the test(s)
- **test_test_imports** list. The list of modules to import in the test suite to
  test to make sure that the package was correctly built
- **test_commands** list. The list of test scripts to be executed

``about:``
- **home_url** string. The url that is considered the home page for the project.
  can be obtained from setup.py
- **license** string. The license under which the project is released. Can be
  obtained from setup.py
