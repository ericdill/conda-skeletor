from __future__ import print_function, absolute_import, division
# from conda.cli.conda_argparse import ArgumentParser
from argparse import ArgumentParser
import os
import re
from collections import defaultdict, namedtuple
import pprint
import yaml
import logging
import tempfile
import subprocess
import shutil
from jinja2 import Environment, FileSystemLoader
from . import git
import depfinder
from . import setup_parser

logger = logging.getLogger(__name__)

try:
    # python 3+
    FileExistsError
except NameError:
    # python 2.7
    FileExistsError = OSError

DEFAULT_BUILD_BASH = """#!/bin/bash
$PYTHON setup.py build
$PYTHON setup.py install --single-version-externally-managed"""

NPY_BUILD_STRING = ("{{ environ.get('GIT_BUILD_STR', '') }}_np{{ np }}"
                    "py{{ py }}")
PY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_py{{ py }}"

# keys are the package name (that you import)
# values are the names that you would find on conda/pypi
_PACKAGE_MAPPING = {
    'skimage': 'scikit-image',
    'netCDF4': 'netcdf4',
    'PIL': 'pillow',
    'IPython': 'ipython',
    'av': 'pyav',
    'cv2': 'opencv',
    'yaml': 'pyyaml',
    'stdlib_list': 'stdlib-list',
    'epics': 'pyepics',
    'xray_vision': 'xray-vision',
    'IPython': 'ipython',
}

conda_skeletor_content = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(conda_skeletor_content, 'templates')
DEFAULT_YAML_PATH = os.path.join(conda_skeletor_content, 'default.yml')
del conda_skeletor_content

def main():
    p = ArgumentParser(
        description="""
Tool for generating conda recipes from source code. The resultant recipe should
need to be only lightly edited, if at all. Many recipes should not even need
to be edited.
""",
    )
    p.add_argument(
        "-o", "--output-dir",
        action='store',
        nargs='?',
        help="Directory to write recipes to (default: %(default)s).",
        default=".",
    )
    p.add_argument(
        "-p", "--path",
        action="store",
        nargs='?',
        help=("Directory of source code from which I should generate a "
              "meta.yaml. Note: Exclusive with --git-url."),
    )
    p.add_argument(
        "-gr", "--git-rev",
        help=("check out a specific commit. This argument ia passed to `git "
              "checkout <arg>`. Note: the repo will be copied to a temp "
              "directory first, then `git clean -xfd`, then `git reset --hard`,"
              "then `git checkout git-rev`"),
        action='store',
        nargs='?'
    )
    p.add_argument(
        "-gu", "--git-url",
        action="store",
        nargs='?',
        help=("Git url that should be used to generate a meta.yaml. Note: "
              "entire repo will be cloned a local temp directory. Note2: "
              "Exclusive with --path.")
    )
    p.add_argument(
        "-c", "--skeletor-config",
        action="store",
        nargs='?',
        help=("Directory which contains the 'skeletor.yml' configuration file "
              "(default: %(default)s). WARNING: ABSOLUTE PATHS ONLY!"),
        default='conda-skeletor.yml',
    )
    p.add_argument(
        "-v", "--verbose",
        help="Enable verbose output (info level logging)",
        action='store_true',
    )
    p.add_argument(
        "-vv", "--very-verbose",
        help="Enable very verbose output (debug level logging)",
        action='store_true',
    )

    # TODO
    # p.add_argument(
    #     "--recursive",
    #     action='store_true',
    #     help='Create recipes for dependencies if they do not already exist.'
    # )

    p.set_defaults(func=execute)

    args = p.parse_args()

    if args.verbose:
        from . import logger as mainlogger
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        mainlogger.setLevel(logging.INFO)
        mainlogger.addHandler(handler)

    if args.very_verbose:
        from . import logger as mainlogger
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        mainlogger.setLevel(logging.DEBUG)
        mainlogger.addHandler(handler)

    execute(args, p)


def _regex_tester(test_string, regexers):
    """Helper function to test a string against an iterable of regexers"""
    matched = False
    for regex in regexers:
        matched = (re.compile(regex).match(test_string) is not None) or (regex in test_string)
        if matched:
            break
    return matched


def split_deps(iterable_of_deps_tuples, iterable_of_regexers):
    """Split modules if they match the regex

    Parameters
    ----------
    iterable_of_deps_tuples : iterable
        Output from depfinder.iterate_over_library
    iterable_of_regexers : iterable
        Iterable of regexers to
    """
    good = []
    bad = []
    for mod, mod_path, catcher in iterable_of_deps_tuples:
        # try the module name first
        mod_match = _regex_tester(mod, iterable_of_regexers)
        if not mod_match:
            # if the module name did not match, try the full path
            mod_match = _regex_tester(mod_path, iterable_of_regexers)
        if mod_match:
            good.append((mod, mod_path, catcher))
            mod_match = False
        else:
            bad.append((mod, mod_path, catcher))

    return good, bad


def get_run_requires(iterable_of_deps_tuples, blacklisted_packages=None):
    """Find the runtime dependencies

    Parameters
    ----------
    iterable_of_deps_tuples : Iterable
        Should be an iterable where each element is a tuple/list with
        (module_name, full_module_path, depfinder.ImportCatcher)
    user_config : dict
        Dictionary read in from conda-skeletor.yml

    Returns
    -------
    list
        List of runtime dependencies
    """
    if blacklisted_packages is None:
        blacklisted_packages = []
    run_requires = set()
    for mod_name, path_to_module, catcher in iterable_of_deps_tuples:
        for mod in catcher.required_modules.union(catcher.sketchy_modules):
            if mod in blacklisted_packages:
                continue
            run_requires.add(mod)
    return sorted(list(run_requires))


def construct_template_info(repo_path, setup_info, user_config=None,
                            setup_deps=None):
    if setup_deps is None:
        setup_deps = {}
    if user_config is None:
        user_config = {}
    template_info = {}
    template_info['packagename'] = user_config.get('packagename',
                                                   setup_info.get('name', ''))
    logger.info('setuppy_path = %s' % repo_path)
    version_string = git.describe(repo_path, '', '.post')

    if '.post' in version_string:
        full_hash = subprocess.check_output(['git', "rev-parse", "HEAD"],
                                            cwd=repo_path).decode()
        template_info['source_rev'] = full_hash
    else:
        # TODO consider replacing the assignment with a get for 'git_rev' in
        # the ArgumentParser and then falling back to version_string if that
        # fails.
        template_info['source_rev'] = version_string

    template_info['packageversion'] = version_string
    if 'patches' in user_config:
        template_info['patches'] = user_config['patches']
    if version_string:
        template_info['git'] = True
        # allow the user to overwrite the source url
        template_info['source_url'] = user_config.get('url',
                                                      setup_info.get('url',
                                                                     ''))

    # allow the user to overwrite the build number
    template_info['build_number'] = user_config.get('build_number', 0)
    build_requirements = setup_deps.get('required', {})
    # remove blacklisted packages from the build
    build_requirements = [dep for dep in build_requirements if dep not in
                          user_config.get('blacklist_packages', [])]
    # add the build deps to the template info
    template_info['build_requirements'] = build_requirements

    if 'numpy' in build_requirements:
        build_string = NPY_BUILD_STRING
    else:
        build_string = PY_BUILD_STRING

    # allow the user to overwrite the build string
    template_info['build_string'] = user_config.get('build_string',
                                                    build_string)
    # allow the user to overwrite the home url
    template_info['home_url'] = user_config.get('home_url',
                                                template_info['source_url'])
    # raise if there is no license in either the setup_info or the user_config
    template_info['license'] = setup_info.get('license',
                                              user_config['license'])
    return template_info


def find_test_imports(importable_lib_name, iterable_of_deps_tuples):
    logger.info('Entering find_test_imports')
    logger.info('importable_lib_name = %s', importable_lib_name)
    logger.info('iterable_of_deps_tuples = %s', iterable_of_deps_tuples)

    def into_importable(full_module_path, lib_name):
        if lib_name[-1] != os.sep:
            lib_name += os.sep
        logger.info("%s is going to be split on %s", full_module_path, lib_name)
        relative_module_path = full_module_path.split(lib_name)[-1]
        logger.info("relative_module_path = %s", relative_module_path)
        # trim the '.py'
        relative_module_path = relative_module_path[:-3]
        # add the library name back in
        relative_module_path = lib_name + relative_module_path
        importable_path = '.'.join(relative_module_path.split(os.sep))
        # turn imports from 'foo.bar.baz.__init__' into 'foo.bar.baz'
        if importable_path.endswith('__init__'):
            importable_path = importable_path[:-9]
        # turn the string from path/to/module to path.to.module
        return importable_path

    all_imports = [into_importable(full_path, importable_lib_name)
                   for mod_name, full_path, catcher in iterable_of_deps_tuples]
    all_imports = sorted(all_imports)
    logger.info('Returning all_imports = %s', all_imports)
    return sorted(all_imports)


def execute(args, parser):
    """To match the API of conda-build"""
    path = getattr(args, 'path', None)
    git_url = getattr(args, 'git_url', None)
    git_rev = getattr(args, 'git_rev', None)

    if path is None and git_url is None:
        raise ValueError("You need to provide me with a --path to source code "
                         "or a --git-url to a git repository")
    if path is not None and git_url is not None:
        raise ValueError("Please only give me one of --path or --git-url. You "
                         "gave me both. I do not know what do with both.")

    if path:
        # the user has requested that we look at some local source code.
        # If they are also asking for a specific git tag, we should copy the
        # source directory to a temporary location and then clean the source
        # dir and check out the tag that they asked for
        # an alternative option would be to
        # subprocess.call(['git', 'stash'], cwd=path)
        # old_git_tag = subprocess.check_output(['git', 'describe'], cwd=path)
        # subprocess.call(['git', 'checkout', git_rev], cwd=path)
        # run conda skeletor
        # subprocess.call(['git', 'checkout', old_git_tag], cwd=path)
        # subprocess.call(['git', 'stash', 'pop'], cwd=path)
        path = os.path.abspath(path)
        libname = [s for s in path.split(os.sep) if s][-1]
        logger.info('path = %s' % path)
        logger.info('libname = %s' % libname)
        tempdir = os.path.join(tempfile.gettempdir(), libname)
        logger.info("Copying %s to %s" % (path, tempdir))
        try:
            shutil.copytree(path, tempdir)
        except FileExistsError:
            # This repo has already been copied to a temporary location
            logger.info("Repo already exists at %s. Cleaning with `git clean "
                        "-xfd`" % tempdir)
            subprocess.Popen(['git', 'clean', '-xfd'], cwd=tempdir)
            pass
        path = tempdir

    if git_url:
        path = git.clone(git_url)


    if git_rev:
        logger.info('Checking out %s' % git_rev)
        git.checkout(git_rev, path)

    logger.info('\nInput arguments'
                '\n---------------')
    logger.info('args from ArgumentParser')
    logger.info(pprint.pformat(vars(args)))
    execute_programmatically(args.skeletor_config, path,
                             args.output_dir)


def execute_programmatically(skeletor_config_path, source_path, output_dir):
    """Execute conda skeletor

    Parameters
    ----------
    skeletor_config_path : str
        Path to the skeletor config yaml. Typically named 'conda-skeletor.yml'
    source_path : str
        Path to the source code for which a full conda recipe is to be
        generated.
    output_dir : str
        Directory in which the generated conda recipe is to be placed. Will be
        made if it does not already exist
    """
    if source_path == '.':
        source_path = os.path.abspath(source_path)
    # load the default configuration info
    skeletor_config = defaultdict(list)
    with open(DEFAULT_YAML_PATH) as f:
        skeletor_config.update(yaml.load(f.read()))

    logger.info("\nDefault configuration"
                "\n---------------------")
    logger.info(pprint.pformat(skeletor_config))


    # make sure the skeletor_config_path is an absolute path
    skeletor_config_path = os.path.expanduser(skeletor_config_path)
    skeletor_config_path = os.path.abspath(skeletor_config_path)

    skeletor_config = defaultdict(list)
    with open(skeletor_config_path) as f:
        skeletor_config.update(yaml.load(f.read()))
    logger.info('\nskeletor-config file'
                '\n--------------------')
    logger.info('path = %s' % skeletor_config_path)
    logger.info(pprint.pformat(skeletor_config))

    # find the dependencies for all modules in the source directory
    repo_deps = list(depfinder.iterate_over_library(source_path))

    logger.info('\nFound %s python files'
                '\n---------------------' % len(repo_deps))
    logger.info('source directory = %s' % source_path)
    paths = [p[1] for p in repo_deps]
    logger.info(pprint.pformat(paths))

    # Compile the regexers listed in the conda-skeleton.yml
    test_regexers = skeletor_config.get('test_regex', [])
    ignore_path_regexers = skeletor_config.get('ignore_path_regex', [])
    include_path_regexers = skeletor_config.get('include_path_regex', [])
    extra_setup_regexers = skeletor_config.get('extra_setup_files_regex', [])

    logger.info('\nComparison strings'
                '\n------------------')
    logger.info('test_regexers = %s' % test_regexers)
    logger.info('ignore_path_regexers = %s' % ignore_path_regexers)
    logger.info('include_path_regexers = %s' % include_path_regexers)
    logger.info('extra_setup_regexers = %s' % extra_setup_regexers)

    ignored, without_ignored = split_deps(repo_deps, ignore_path_regexers)
    setup_files, non_setup_files = split_deps(without_ignored,
                                              extra_setup_regexers)
    if include_path_regexers:
        included, without_included = split_deps(non_setup_files,
                                                include_path_regexers)
    else:
        included = non_setup_files
        without_included = None
    tests, without_tests = split_deps(included, test_regexers)
    logger.info('\nSplitting up the modules'
                '\n------------------------')
    logger.info('\nIgnored modules'
                '\n---------------')
    ignored_paths = [p[1] for p in ignored]
    logger.info(pprint.pformat(ignored_paths))
    logger.info('\nModules to scrape for build dependencies'
                '\n----------------------------------------')
    setup_file_paths = [p[1] for p in setup_files]
    logger.info(pprint.pformat(setup_file_paths))
    logger.info('\nModules to split into test/run time'
                '\n-----------------------------------')
    included_paths = [p[1] for p in included]
    logger.info(pprint.pformat(included_paths))
    if without_included:
        logger.info('\nExcluded'
                    '\n--------')
        excluded_paths = [p[1] for p in without_included]
        logger.info(pprint.pformat(excluded_paths))
    logger.info('\nModules to scrape for testing dependencies'
                '\n------------------------------------------')
    test_paths = [p[1] for p in tests]
    logger.info(pprint.pformat(test_paths))
    logger.info('\nModules to scrape for runtime dependencies'
                '\n------------------------------------------')
    without_test_paths = [p[1] for p in without_tests]
    logger.info(pprint.pformat(without_test_paths))

    def find_lib_name(without_tests):
        """Helper function to find the library name from all non-test modules

        Parameters
        ----------
        without_tests : iterable of (mod_name, full_path, ImportCatcher) tuples
            Pass in the second return argument from `split_deps`

        Returns
        -------
        str
            The name of the library (hopefully!)
        """
        logger.info("\nEntering find_lib_name")
        non_test_paths = [path for name, path, catcher in without_tests]
        common_path = os.path.commonprefix(non_test_paths)
        logger.info('common_path = %s', common_path)
        lib_name = common_path.strip(os.sep).split(os.sep)[-1]
        is_single_module_package = False
        if lib_name.endswith('.py'):
            logger.info("Found that lib_name ends with '.py'. This must be a"
                        "single-module package. Stripping the .py")
            lib_name = lib_name[:-3]
            is_single_module_package = True
        logger.info("Leaving find_lib_name and returning %s", lib_name)
        ret = namedtuple('ReturnVals',
                         ['library_name', 'is_single_module_package'])
        return ret(lib_name, is_single_module_package)

    ret = find_lib_name(without_tests)
    importable_lib_name, is_single_module_package = ret
    skeletor_config['blacklist_packages'].append(importable_lib_name)
    # find the runtime deps
    run_requires = get_run_requires(
        without_tests,
        blacklisted_packages=skeletor_config.get('blacklist_packages')
    )
    logger.info('\nExtracted dependencies'
                '\n----------------------')
    logger.info('Runtime')
    logger.info(pprint.pformat(run_requires))

    # find the testing time deps
    test_requires = get_run_requires(
        tests,
        blacklisted_packages=skeletor_config.get('blacklist_packages')
    )
    logger.info('Test')
    logger.info(pprint.pformat(test_requires))

    logger.info('\nSetup info'
                '\n----------')
    setup_info = None
    for mod_name, full_path, mod_deps in setup_files:
        if('setup.py' in full_path):
            setup_info = (mod_name, full_path, mod_deps)
        logger.info('setup path = %s' % full_path)
        logger.info('setup info = {}'.format(setup_info))

    if setup_info:
        # try:
        setup_info_dict = setup_parser.parse(setup_info[1])
        logger.info("\nInformation scraped from setup.py"
                    "\n---------------------------------")
        logger.info(pprint.pformat(setup_info_dict))
        # except IndexError:
        #     # Occurs when setup.py has a call like setup(**kwargs). Looking
        #     # at you pims...
        #     logger.info("No information gained from setup.py")
        #     setup_info_dict = {}
    else:
        logger.info("No setup.py file found. Is this a python project?")
        setup_info_dict = {}

    # grab the code out of the setup.py file to find its deps so that I can
    # parse the code for imports
    setup_deps = None
    code = ''
    for mod_name, full_path, catcher in setup_files:
        with open(full_path, 'r') as f:
            code += f.read()
    setup_deps = depfinder.get_imported_libs(code).describe()
    # add any setup deps that are included in the setup.py under
    # 'install_requires'
    install_requires = setup_info_dict.get('install_requires', [])
    # make sure that we are not iterating over a string...
    if isinstance(install_requires, str):
        install_requires = [install_requires]
    # add all extra deps in 'install_requires' to build requirements of the
    # conda recipe
    for dep in install_requires:
        setup_deps['required'].add(dep)
    logger.info('\nSetup dependencies'
                '\n------------------')
    logger.info(pprint.pformat(setup_deps))
    # create the git repo path so that I can determine the version string from
    # the source code
    git_repo_path = os.path.dirname(setup_info[1])
    template_info = construct_template_info(git_repo_path, setup_info_dict,
                                            setup_deps=setup_deps,
                                            user_config=skeletor_config)
    # remove self-references
    try:
        run_requires.remove(template_info['packagename'])
    except ValueError:
        pass
    try:
        test_requires.remove(template_info['packagename'])
    except ValueError:
        pass
    build_requirements = template_info['build_requirements']

    # remap deps
    for k, v in _PACKAGE_MAPPING.items():
        if k in run_requires:
            run_requires[run_requires.index(k)] = v
        if k in test_requires:
            test_requires[test_requires.index(k)] = v
        if k in build_requirements:
            build_requirements[build_requirements.index(k)] = v

    template_info['build_requirements'] = build_requirements
    extra_requirements = skeletor_config.get('requirements', {})
    extra_test = extra_requirements.get('test', {})
    for lib in extra_test:
        test_requires.append(lib)
    extra_run = extra_requirements.get('run', {})
    for lib in extra_run:
        run_requires.append(lib)

    run_requires = sorted(run_requires)

    # conda build treats the test_requires sections as a superset of
    # run_requires. No need to explicitly have a long list of test_requirements
    test_requires = sorted(set(test_requires) - set(run_requires))

    template_info['run_requirements'] = run_requires
    template_info['test_requires'] = test_requires

    if 'test_imports' not in template_info:
        if is_single_module_package:
            test_imports = [importable_lib_name]
        else:
            test_imports = find_test_imports(importable_lib_name, without_tests)
        template_info['test_imports'] = test_imports
    logger.info('\nTemplate Information'
                '\n--------------------')
    logger.info(pprint.pformat(template_info))
    # load and render the template
    logger.info('\nTemplate directory'
                '\n------------------'
                '\n%s' % (TEMPLATE_DIR))
    # create the jinja environment
    jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # template.render(**setup_info)
    meta_fname = os.path.join(output_dir, 'meta.yaml')
    try:
        os.makedirs(output_dir)
    except FileExistsError:
        # the file, uh, already exists
        pass
    template = jinja_env.get_template('meta.tmpl')
    meta_yml = template.render(**template_info)

    with open(meta_fname, 'w') as f:
        f.write(meta_yml)
    if skeletor_config['generate_build_script']:
        build_bash_fname = os.path.join(output_dir, 'build.sh')
        with open(build_bash_fname, 'w') as f:
            f.write(DEFAULT_BUILD_BASH)

    logger.info('\nmeta.yaml'
                '\n---------')
    logger.info('\nwritten to: %s' % meta_fname)
    logger.info(meta_yml)
