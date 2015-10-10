import subprocess
import logging
import tempfile
import os
logger = logging.getLogger(__name__)


def clone_to_temp(git_url, git_rev=None):
    """Clone a `git_url` to temp dir and check out `git_rev`

    Parameters
    ----------
    git_url : str
        Git repo to clone
    git_rev : str, optional
        Branch to check out
        Defaults to whatever the repo thinks is the master branch

    Returns
    -------
    path : str
        Full path to root of newly cloned git repo
    """
    if git_rev is None:
        git_rev = 'master'
    tempdir = tempfile.gettempdir()
    sourcedir = os.path.join(tempdir, git_url.strip('/').split('/')[-1])
    # clone the git repo to the target directory
    subprocess.call(['git', 'clone', git_url, sourcedir])
    if git_rev is not None:
        subprocess.call(['git', 'checkout', git_rev], cwd=sourcedir)

    return sourcedir


def git_describe(git_root, version_prefix, version_suffix,
                 use_local_version_id=False):
    """Use git describe to get the version, then format it to PEP440

    Parameters
    ----------
    git_root : str
    version_prefix : str
        Anything to prepend to the version string. commonly 'v'
    verison_suffix : str
        If there are commits to master since the last tag, add `version_suffix`
        between the tag and the number of commits. If version_suffix is
        ".post", then the output string will be 0.2.0.post5, for tag 0.2.0 +
        5 commits.
    use_local_version_id : bool, optional
        Defaults to False
        Include the first six characters of the git hash at the end of the
        version string, separated by a '+' from the rest of the version string

    Returns
    -------
    version : str
        The version string, formatted according to PEP440, with a 'dirty' tag
        if you are not building from uncommitted code. The 'dirty' tag is
        non-configurable. If you are building from uncommitted code, shame on
        you.
        {version_prefix}GIT_TAG{version_suffix}[+{local_version_id}][(+.)dirty]
    """
    git_describe_cmd = ['git', 'describe', '--dirty', '--long',
                        '--always', '--tags']
    desc = subprocess.check_output(git_describe_cmd, cwd=git_root).strip()
    if isinstance(desc, bytes):
        desc = desc.decode('utf8')
    split_desc = desc.split('-')
    logger.debug('split_desc = %s', split_desc)

    dirty = ''
    # man this is going to be a terrible bug when the first six characters of
    # the git hash contain `dirty`
    if 'dirty' in split_desc[-1]:
        dirty = split_desc.pop(-1)

    prefix, suffix, local_id = split_desc

    # add the prefix if you didn't tag it like you wanted it
    if not prefix.startswith(version_prefix):
        prefix = version_prefix + prefix

    # if there have been commits to the repo since the tag, then add the
    # suffix, otherwise do not
    if int(suffix) > 0:
        version = prefix + version_suffix + suffix
    else:
        version = prefix
    # add the local identifier (the first bit of the git hash) to the version
    if use_local_version_id:
        # PEP440 formatting of the local identifier
        version += '+' + local_id
    if dirty:
        # if you're building from uncommitted repos, shame on you...
        if '+' not in version:
            version += '+'
        else:
            version += '.'
        version += dirty

    return version
