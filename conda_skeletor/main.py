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
from conda.cli.conda_argparse import ArgumentParser
from jinja2 import Environment, FileSystemLoader
import whatsmyversion
import os
import depfinder
from . import setup_parser
from pprint import pprint as print
from collections import deque
import yaml

NPY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_np{{ np }}py{{ py }}"
PY_BUILD_STRING = "{{ environ.get('GIT_BUILD_STR', '') }}_py{{ py }}"


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
    build_deps = setup_deps.get('required', {})
    # remove blacklisted packages from the build
    build_deps = [dep for dep in build_deps
                  if dep not in user_config.get('blacklist_packages', [])]
    # add the build deps to the template info
    template_info['build_deps'] = build_deps

    if 'numpy' in build_deps:
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
    # drop any deps that contain something in 'ignore_path'
    cleaned_deps = deque()
    ignore = False
    for mod_name, full_path, mod_deps in repo_deps:
        for ignore_pattern in skeletor_config['ignore_path']:
            if ignore_pattern in full_path:
                ignore = True
        if ignore:
            ignore = False
            print('skipping = %s' % full_path)
            continue
        cleaned_deps.append((mod_name, full_path, mod_deps))
        print('path = %s' % full_path)

    setup_info = None
    for mod_name, full_path, mod_deps in cleaned_deps:
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

    # add the run time deps to the template

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
