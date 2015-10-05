
import os
import subprocess
import tempfile


def test_skxray_meta_generation():
    with open(os.path.join(os.path.dirname(__file__), 'test_data', 'skxray.meta.yaml')) as f:
        target_meta_yaml = f.read()
    #TODO grab the url/rev out of the target meta. It fails now because of jinja templating being in the yaml
    # target = yaml.load(TARGET_META)
    # git_rev = target['source']['git_rev']
    # git_url = target['source']['git_url']
    git_url = 'http://github.com/scikit-xray/scikit-xray'
    git_rev = '7d6d0b5919d48df4b9f733c3112b344135eab701'

    tempdir = tempfile.gettempdir()
    output_dir = tempfile.TemporaryDirectory().name
    os.mkdir(output_dir)
    target_directory = os.path.join(tempdir, git_url.strip('/').split('/')[-1])

    # clone the git repo to the target directory
    subprocess.call(['git', 'clone', git_url, os.path.join(tempdir, target_directory)])
    subprocess.call(['git', 'checkout', git_rev], cwd=target_directory)
    subprocess.call(['conda-skeletor', '--skeletor-config',
                     '/home/edill/dev/conda/conda-skeletor/example/conda-skeletor.yml',
                     '--output-dir', output_dir,
                     target_directory])
    with open(os.path.join(output_dir, 'meta.yaml'), 'r') as f:
        generated_meta_yaml = f.read()
    print('generated meta yaml')
    print(generated_meta_yaml)
    print('expected meta yaml')
    print(target_meta_yaml)
    assert generated_meta_yaml == target_meta_yaml