from conda_skeletor.git import clone


def test_git_clone():
    """Smoketest to make sure an exception isn't thrown on duplicate clone calls
    """
    clone('http://github.com/ericdill/conda-skeletor')
    clone('http://github.com/ericdill/conda-skeletor')
