import subprocess
import logging
logger = logging.getLogger(__name__)


def git_describe(git_root, version_prefix, version_suffix, use_local_version_id=False):
    git_describe_cmd = ['git', 'describe', '--dirty', '--long', '--always', '--tags']
    desc = subprocess.check_output(git_describe_cmd, cwd=git_root).strip()
    if isinstance(desc, bytes):
        desc = desc.decode('utf8')
    # get the partial git hash. This will inform us which part of the git describe is
    # part of the 'local version identifier'
    full_hash = subprocess.check_output(['git', "rev-parse", "HEAD"],
                                        cwd=git_root).decode()
    partial_hash = full_hash[:7]
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
        if not '+' in version:
            version += '+'
        else:
            version += '.'
        version += dirty

    return version