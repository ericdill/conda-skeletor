
import os
import subprocess
import tempfile
import shutil
import conda_skeletor

SOURCE_DIR = None
OUTPUT_DIR = None
TARGET_META_YAML = None
SKELETOR_CONFIG_PATH = None

def setup_module():
    global OUTPUT_DIR, SOURCE_DIR, TARGET_META_YAML, SKELETOR_CONFIG_PATH
    with open(os.path.join(os.path.dirname(__file__),
                           'depfinder.meta.yaml')) as f:
        TARGET_META_YAML = f.read()
    SKELETOR_CONFIG_PATH = os.path.join(os.path.dirname(__file__),
                                        'depfinder.conda-skeletor.yml')
    #TODO grab the url/rev out of the target meta. It fails now because of
    # jinja templating in the yaml
    # target = yaml.load(TARGET_META)
    # git_rev = target['source']['git_rev']
    # git_url = target['source']['git_url']
    git_url = 'http://github.com/ericdill/depfinder'
    git_rev = '56452cccb676ab73c96eb8a00f883c99f081fb7e'

    tempdir = tempfile.gettempdir()
    OUTPUT_DIR = tempfile.mkdtemp()
    SOURCE_DIR = os.path.join(tempdir, git_url.strip('/').split('/')[-1])

    # clone the git repo to the target directory
    subprocess.call(['git', 'clone', git_url, SOURCE_DIR])
    subprocess.call(['git', 'checkout', git_rev], cwd=SOURCE_DIR)


def teardown_module():
    global OUTPUT_DIR, SOURCE_DIR
    shutil.rmtree(OUTPUT_DIR)
    shutil.rmtree(SOURCE_DIR)


def test_depfinder_meta_generation():
    global OUTPUT_DIR, SOURCE_DIR
    conda_skeletor.execute_programmatically(SKELETOR_CONFIG_PATH, SOURCE_DIR,
                                            OUTPUT_DIR)
    with open(os.path.join(OUTPUT_DIR, 'meta.yaml'), 'r') as f:
        generated_meta_yaml = f.read()
    assert generated_meta_yaml == TARGET_META_YAML


def test_programmatic_excecution():
    global OUTPUT_DIR, SOURCE_DIR
    subprocess.call(['conda-skeletor', '--skeletor-config',
                     SKELETOR_CONFIG_PATH, '--output-dir', OUTPUT_DIR,
                     SOURCE_DIR])
    with open(os.path.join(OUTPUT_DIR, 'meta.yaml'), 'r') as f:
        generated_meta_yaml = f.read()
    print('generated meta yaml')
    print(generated_meta_yaml)
    print('TARGET_META_YAML')
    print(TARGET_META_YAML)
    assert generated_meta_yaml == TARGET_META_YAML