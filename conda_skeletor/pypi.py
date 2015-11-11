"""Module to grab information from pypi"""

import requests
import json


PYPI_URL = 'https://pypi.python.org/pypi/{}/json'


def description(package_name):
    url = PYPI_URL.format(package_name)
    info = requests.get(url)
    if info.status_code == 200:
        info = json.loads(info.text)
        return info['info']['summary']

    raise ValueError("Status code returned is %s for url = %s" %
                     (info.status_code, url))

