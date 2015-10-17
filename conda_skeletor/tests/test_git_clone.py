from conda_skeletor.git import clone


def test_git_clone():
    clone('http://github.com/ericdill/conda-skeletor')
    clone('http://github.com/ericdill/conda-skeletor')
