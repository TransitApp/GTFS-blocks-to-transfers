#!/usr/bin/env python3
"""
Manual install script for restricted environments where pip is not working.
"""

import urllib.request
import zipfile
import io
import tempfile
from pathlib import Path
import dependency_info


def install_from_github(org, project, version, modname):
    url = f'https://github.com/{org}/{project}/archive/refs/tags/v{version}.zip'
    dest = Path(__file__).resolve().parent
    print(f'Downloading {url}')

    with urllib.request.urlopen(url) as data:
        data_stream = io.BytesIO(data.read())
        archive = zipfile.ZipFile(data_stream)

    with tempfile.TemporaryDirectory() as tmpdir: 
        print('Extracting...')
        archive.extractall(tmpdir)
        install_path = dest / modname
        print(f'Installing to {install_path}')
        module_contents = Path(tmpdir) / f'{project}-{version}' / modname
        module_contents.rename(dest / modname)


def get_dependencies():
    install_from_github(
            'TransitApp', 'py-gtfs-loader', 
            dependency_info.py_gtfs_loader, 
            'gtfs_loader')


if __name__ == '__main__':
    get_dependencies()
