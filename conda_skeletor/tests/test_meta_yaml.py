import yaml
import pytest
import os
from os import path
import subprocess
import tempfile
import shutil
import re

import conda_skeletor
from conda_skeletor.git import clone_to_temp


data_path = path.join(path.dirname(__file__), 'data')
projects_to_test = [path.join(data_path, folder) for folder in os.listdir(data_path)]

@pytest.mark.parametrize("data_path", projects_to_test)
def test_meta_generation(data_path):
    # set up
    target_as_dict = safe_yaml_read(path.join(data_path, 'target.meta.yaml'))
    with open(path.join(data_path, 'target.meta.yaml'), 'r') as f:
        target_as_string = f.read()

    skeletor_config_path = path.join(data_path, 'conda-skeletor.yml')
    print('skeletor_config_path: %s' % skeletor_config_path)
    git_url = target_as_dict['source']['git_url']
    git_rev = target_as_dict['source']['git_rev']

    # clone the repo to a temporary directory
    source_dir = clone_to_temp(git_url, git_rev)

    # run tests
    programmatic_path = generate_programmatically(source_dir,
                                                  skeletor_config_path)
    programmatic_yaml_path = os.path.join(programmatic_path, 'meta.yaml')
    assert safe_yaml_read(programmatic_yaml_path) == target_as_dict
    with open(programmatic_yaml_path, 'r') as f:
        programmatic_text = f.read()
    assert programmatic_text == target_as_string

    cli_path = generate_cli_local_source(source_dir, skeletor_config_path)
    cli_yaml_path = os.path.join(cli_path, 'meta.yaml')
    assert safe_yaml_read(cli_yaml_path) == target_as_dict
    with open(cli_yaml_path, 'r') as f:
        cli_text = f.read()
    assert cli_text == target_as_string

    # tear down
    shutil.rmtree(cli_path)
    shutil.rmtree(programmatic_path)
    shutil.rmtree(source_dir)


def generate_programmatically(source_dir, skeletor_config_path):
    output_dir = tempfile.mkdtemp()
    conda_skeletor.execute_programmatically(
        skeletor_config_path, source_dir, output_dir)
    return output_dir


def generate_cli_local_source(source_dir, skeletor_config_path):
    output_dir = tempfile.mkdtemp()
    subprocess.call(['conda-skeletor', '--skeletor-config',
                     skeletor_config_path, '--output-dir', output_dir,
                     '-p', source_dir])
    return output_dir


def safe_yaml_read(fpath, replace_str=''):
    """
    Reads a yaml file stripping all of the jinja templating markup
    Parameters
    ----------
    fpath : str
        Path to yaml file to sanitize
    replace_str : str
        String to replace the template markup with, defaults to ''.
    Returns
    -------
    yaml_dict : dict
        The dictionary with all of the jinja2 templating fields
        replaced with ``replace_str``.
    """
    with open(fpath, 'r') as f:
        lns = []
        for ln in f:
            lns.append(re.sub(r'{[{%].*?[%}]}', '', ln))
    meta_dict = yaml.load(''.join(lns))
    return meta_dict