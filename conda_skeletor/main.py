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
import whatsmyversion
import os
import re
import depfinder
from . import setup_parser
from pprint import pprint as print
from collections import deque
import yaml

NPY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_np{{ np }}py{{ py }}"
PY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_py{{ py }}"

package_mapping = {
    'skimage': 'scikit-image'
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
        nargs=1,
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
        nargs=1,
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
    template_info['packagename'] = setup_info['name']
    print('setuppy_path = %s' % repo_path)
    version_string = whatsmyversion.git_describe(repo_path, 'v', '.post')
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
        template_info['source_url'] = user_config.get('url', setup_info['url'])

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
    template_info['license'] = setup_info['license']
    return template_info

def execute(args, parser):
    print("I'm supposed to make a meta.yaml file now.")
    print('args = %s' % args)

    with open(args.skeletor_config) as f:
        skeletor_config = yaml.load(f.read())

    print('loaded config = %s' % skeletor_config)

    # find the dependencies for all modules in the source directory
    repo_deps = depfinder.iterate_over_library(args.source)

    # Compile the regexers listed in the conda-skeleton.yml
    test_regexers = [re.compile(reg) for reg in skeletor_config.get('test_regex', [])]
    ignore_path_regexers = [re.compile(reg) for reg in skeletor_config.get('ignore_path_regex', [])]
    include_path_regexers = [re.compile(reg) for reg in skeletor_config.get('include_path_regex', [])]
    ignored, without_ignored = split_deps(repo_deps, ignore_path_regexers)
    included, without_included = split_deps(without_ignored, include_path_regexers)
    tests, without_tests = split_deps(included, test_regexers)

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
        setup_info_dict = setup_parser.parse(setup_info[1])
        print('setup_info\n')
        print(setup_info_dict)
    else:
        print("No setup.py file found. Is this a python project?")
        raise

    # grab the code out of the setup.py file to find its deps so that I can
    # parse the code for imports
    setup_deps = None
    with open(setup_info[1], 'r') as f:
        code = f.read()
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
        template_info['test_imports'] = [template_info['packagename']]

    print('template_info')
    print(template_info)
    # load and render the template
    tmplt_dir = os.path.join(conda_skeletor_content, 'templates')
    # create the jinja environment
    jinja_env = Environment(loader=FileSystemLoader([
        os.path.join(args.output_dir, 'conda-recipe'),
        tmplt_dir
    ]))

    template = jinja_env.get_template('meta.tmpl')
    # template.render(**setup_info)
    target_fname = os.path.join(args.output_dir, 'meta.yaml')
    with open(target_fname, 'w') as fh:
        fh.write(template.render(**template_info))
