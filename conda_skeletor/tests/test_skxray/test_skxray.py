
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
                           'skxray.meta.yaml')) as f:
        TARGET_META_YAML = f.read()
    SKELETOR_CONFIG_PATH = os.path.join(os.path.dirname(__file__),

                                        'skxray.conda-skeletor.yml')
    #TODO grab the url/rev out of the target meta. It fails now because of jinja templating being in the yaml
    # target = yaml.load(TARGET_META)
    # git_rev = target['source']['git_rev']
    # git_url = target['source']['git_url']
    git_url = 'http://github.com/scikit-xray/scikit-xray'
    git_rev = '7d6d0b5919d48df4b9f733c3112b344135eab701'

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


def test_skxray_meta_generation():
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