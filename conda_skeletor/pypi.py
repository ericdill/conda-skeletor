"""Module to grab information from pypi"""

import requests
import json
import logging

logger = logging.getLogger(__name__)

PYPI_URL = 'https://pypi.python.org/pypi/{}/json'
CONDA_URL = 'http://repo.continuum.io/pkgs/metadata.json'

conda_info = None


def description(package_name, pypi_first=False, split_on_whitespace=True):
    """Get the short summary description of the library called `package_name`

    Parameters
    ----------
    package_name : str
        The name of the package. This is the name that you `pip install
        <package_name>`, not the name that you `import <package_name>`
    pypi_first : bool, optional
        Defaults to True.
        If True: Search pypi for the summary first.
        If False: Search conda for the summary first.
    split_on_whitespace : bool, optional
        Defaults to True.
        You would want to split on whitespace if your library has a specified
        version, such as 'pymongo <3'.
    """
    call_order = [('pypi', _pypi), ('conda', _conda)]
    if split_on_whitespace:
        package_name = package_name.split(' ')[0]

    if not pypi_first:
        call_order.reverse()

    summary = ''
    for identifier, call in call_order:
        try:
            summary_string = call(package_name)
        except ValueError:
            pass
        else:
            # format the summary string and quit the for loop
            summary = '%s (%s)' % (summary_string, identifier)
            break

    if not summary:
        # no package info was found, use a default string
        summary = ('No package info found for %s at any of these locations: '
                   '%s' % (package_name,
                           [identifier for identifier, call in call_order]))
    return summary


def _conda(package_name):
    global conda_info
    if not conda_info:
        info = requests.get(CONDA_URL)
        if info.status_code == 200:
            conda_info = json.loads(info.text)

    try:
        summary = conda_info[package_name]['summary']
    except KeyError:
        raise ValueError("conda metadata does not contain information on "
                         "package %s" % package_name)

    return summary

def _pypi(package_name):
    url = PYPI_URL.format(package_name)
    info = requests.get(url)
    if info.status_code == 200:
        info = json.loads(info.text)
        return info['info']['summary']

    logger.info("Status code returned is %s for url = %s" %
                (info.status_code, url))
    raise ValueError('pypi search for info regarding %s was unsuccessful' %
                     package_name)
