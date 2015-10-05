# conda-skeletor
# Copyright (C) 2015 Eric Dill
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function, absolute_import, division
# from conda.cli.conda_argparse import ArgumentParser
from argparse import ArgumentParser
from jinja2 import Environment, FileSystemLoader
import os
import re
from . import git
import depfinder
from . import setup_parser
from pprint import pprint as print
from collections import deque
import yaml

DEFAULT_BUILD_BASH = """#!/bin/bash
$PYTHON setup.py build
$PYTHON setup.py install"""

NPY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_np{{ np }}py{{ py }}"
PY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_py{{ py }}"

package_mapping = {
    'skimage': 'scikit-image',
    'netCDF4': 'netcdf4',
    'PIL': 'pillow',
    'IPython': 'ipython',
    'av': 'pyav',
    'cv2': 'opencv',
    'yaml': 'pyyaml',
}

conda_skeletor_content = os.path.abspath(os.path.dirname(__file__))

def main():
    p = ArgumentParser(
        description="""
Tool for generating conda recipes from source code. These should need to be
only lightly edited, if at all. Many recipes should not even need to be edited.
        """,
    )
    p.add_argument(
        "--output-dir",
        action='store',
        nargs='?',
        help="Directory to write recipes to (default: %(default)s).",
        default=".",
    )
    p.add_argument(
        "source",
        action="store",
        nargs='?',
        help="Directory of source code from which I should generate a meta.yaml",
    )
    p.add_argument(
        "--skeletor-config",
        action="store",
        nargs='?',
        help=("Directory which contains the 'skeletor.yml' configuration file "
              "(default: %(default)s). WARNING: ABSOLUTE PATHS ONLY!"),
        default='conda-skeletor.yml',
    )

    # TODO
    # p.add_argument(
    #     "--recursive",
    #     action='store_true',
    #     help='Create recipes for dependencies if they do not already exist.'
    # )

    p.set_defaults(func=execute)

    args = p.parse_args()

    execute(args, p)


def _regex_tester(test_string, regexers):
    """Helper function to test a string against an iterable of regexers"""
    matched = False
    for regex in regexers:
        if regex.__class__.__name__ == 'SRE_Pattern':
            matched = regex.match(test_string) is not None
        else:
            matched = regex in test_string
        if matched:
            break
    return matched


def split_deps(iterable_of_deps_tuples, iterable_of_regexers):
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


def get_runtime_deps(iterable_of_deps_tuples, blacklisted_packages=None):
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
    runtime_deps = set()
    for mod_name, path_to_module, catcher in iterable_of_deps_tuples:
        for mod in catcher.required_modules.union(catcher.sketchy_modules):
            if mod in blacklisted_packages:
                continue
            runtime_deps.add(mod)
    return sorted(list(runtime_deps))

def construct_template_info(repo_path, setup_info, user_config=None,
                            setup_deps=None):
    if setup_deps is None:
        setup_deps = {}
    if user_config is None:
        user_config = {}
    template_info = {}
    template_info['packagename'] = user_config.get('name', setup_info.get('name', ''))
    print('setuppy_path = %s' % repo_path)
    version_string = git.git_describe(repo_path, 'v', '.post')
    import subprocess
    if '.post' in version_string:
        full_hash = subprocess.check_output(['git', "rev-parse", "HEAD"],
                                            cwd=repo_path).decode()
        template_info['source_rev'] = full_hash
    else:
        template_info['source_rev'] = version_string

    template_info['packageversion'] = version_string

    if version_string:
        template_info['git'] = True
        # allow the user to overwrite the source url
        template_info['source_url'] = user_config.get('url', setup_info.get('url', ''))

    # allow the user to overwrite the build number
    template_info['build_number'] = user_config.get('build_number', 0)
    build_requirements = setup_deps.get('required', {})
    # remove blacklisted packages from the build
    build_requirements = [dep for dep in build_requirements
                  if dep not in user_config.get('blacklist_packages', [])]
    # add the build deps to the template info
    template_info['build_requirements'] = build_requirements

    if 'numpy' in build_requirements:
        build_string = NPY_BUILD_STRING
    else:
        build_string = PY_BUILD_STRING

    # allow the user to overwrite the build string
    template_info['build_string'] = user_config.get('build_string', build_string)
    # allow the user to overwrite the home url
    template_info['home_url'] = user_config.get('home_url', template_info['source_url'])
    template_info['license'] = setup_info.get('license', '')
    return template_info

def find_test_imports(importable_lib_name, iterable_of_deps_tuples):
    print('finding test imports')
    paths = []
    def into_importable(full_module_path, lib_name):
        relative_module_path = full_module_path.split(lib_name, maxsplit=1)[1]
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
    return sorted(all_imports)

def execute(args, parser):
    """To match the API of conda-build"""
    print("I'm supposed to make a meta.yaml file now.")
    print('args = %s' % args)
    execute_programmatically(args.skeletor_config, args.source,
                             args.output_dir)


def execute_programmatically(skeletor_config_path, source_path, output_dir):

    with open(skeletor_config_path) as f:
        skeletor_config = yaml.load(f.read())

    print('loaded config = %s' % skeletor_config)

    # find the dependencies for all modules in the source directory
    repo_deps = list(depfinder.iterate_over_library(source_path))

    # Compile the regexers listed in the conda-skeleton.yml
    test_regexers = [re.compile(reg) for reg in skeletor_config.get('test_regex', [])]
    ignore_path_regexers = [re.compile(reg) for reg in skeletor_config.get('ignore_path_regex', [])]
    include_path_regexers = [re.compile(reg) for reg in skeletor_config.get('include_path_regex', [])]
    extra_setup_regexers = [re.compile(reg) for reg in skeletor_config.get('extra_setup_files_regex', [])]
    print('extra_setup_regexers')
    print(extra_setup_regexers)
    ignored, without_ignored = split_deps(repo_deps, ignore_path_regexers)
    setup_files, _ = split_deps(repo_deps, extra_setup_regexers)
    included, without_included = split_deps(without_ignored, include_path_regexers)
    tests, without_tests = split_deps(included, test_regexers)

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
        non_test_paths = [full_path for mod_name, full_path, catcher in without_tests]
        common_path = os.path.commonprefix(non_test_paths)
        return common_path.strip(os.sep).split(os.sep)[-1]

    importable_lib_name = find_lib_name(without_tests)
    skeletor_config['blacklist_packages'].append(importable_lib_name)
    # find the runtime deps
    runtime_deps = get_runtime_deps(
        without_tests,
        blacklisted_packages=skeletor_config.get('blacklist_packages')
    )
    print('runtime_deps')
    print(runtime_deps)

    # find the testing time deps
    test_requires = get_runtime_deps(
        tests,
        blacklisted_packages=skeletor_config.get('blacklist_packages')
    )
    print('test time deps')
    print(test_requires)

    setup_info = None
    for mod_name, full_path, mod_deps in without_ignored:
        if('setup.py' in full_path):
            setup_info = (mod_name, full_path, mod_deps)

    if setup_info:
        try:
            setup_info_dict = setup_parser.parse(setup_info[1])
            print('setup_info\n')
            print(setup_info_dict)
        except IndexError:
            # Occurs when setup.py has a call like setup(**kwargs). Looking at
            # you pims...
            setup_info_dict = {}
    else:
        print("No setup.py file found. Is this a python project?")
        raise

    # grab the code out of the setup.py file to find its deps so that I can
    # parse the code for imports
    setup_deps = None
    code = ''
    for mod_name, full_path, catcher in setup_files:
        with open(full_path, 'r') as f:
            code += f.read()
    setup_deps = depfinder.get_imported_libs(code).describe()
    print('setup_deps')
    print(setup_deps)
    # create the git repo path so that I can determine the version string from
    # the source code
    git_repo_path = os.path.dirname(setup_info[1])
    template_info = construct_template_info(git_repo_path, setup_info_dict,
                                            setup_deps=setup_deps,
                                            user_config=skeletor_config)

    # remove self-references
    try:
        runtime_deps.remove(template_info['packagename'])
    except ValueError:
        pass
    try:
        test_requires.remove(template_info['packagename'])
    except ValueError:
        pass

    # remap deps
    for k, v in package_mapping.items():
        if k in runtime_deps:
            runtime_deps.remove(k)
            runtime_deps.append(v)
        if k in test_requires:
            test_requires.remove(k)
            test_requires.append(v)

    template_info['run_requirements'] = runtime_deps
    template_info['test_requires'] = test_requires

    if 'test_imports' not in template_info:
        template_info['test_imports'] = find_test_imports(importable_lib_name,
                                                          without_tests)

    print('template_info')
    print(template_info)
    # load and render the template
    template_dir = os.path.join(conda_skeletor_content, 'templates')
    print('template directory = %s' % template_dir)
    # create the jinja environment
    jinja_env = Environment(loader=FileSystemLoader(template_dir))

    if skeletor_config.get('generate_test_suite', 'False'):
        if 'nose' in test_requires:
            template_info['test_commands'] = ['nosetests -v %s' % importable_lib_name]
        elif 'pytest' in test_requires:
            template_info['test_commands'] = ['py.test -v %s' % importable_lib_name]


    template = jinja_env.get_template('meta.tmpl')
    # template.render(**setup_info)
    meta_fname = os.path.join(output_dir, 'meta.yaml')
    with open(meta_fname, 'w') as f:
        f.write(template.render(**template_info))

    build_bash_fname = os.path.join(output_dir, 'build.sh')
    with open(build_bash_fname, 'w') as f:
        f.write(DEFAULT_BUILD_BASH)
