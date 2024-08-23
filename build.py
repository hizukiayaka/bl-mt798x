#!/usr/bin/env python3

import argparse
import io
import subprocess

from git import Repo
from tarfile import TarFile

def check_build_directory(sub_mod):
    mod_name = sub_mod.name
    build_dir = 'build-{0}'.format(mod_name)

    with io.BytesIO() as tardata:
        with Repo(sub_mod) as repo:
            repo.archive(tardata)
        tardata.seek(0)
        with TarFile(fileobj=tardata) as tmp_tar:
            tmp_tar.extractall(path=build_dir, filter='tar')

def prepare_submodule():
    repo = Repo()
    sms = repo.submodules

    [check_build_directory(sm) for sm in sms]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='build.py')
    parser.add_argument('step', choices=['unpack', 'patch', 'config', \
                                          'build', 'firmware'])

    args = parser.parse_args()

    match args.step:
        case 'unpack':
            prepare_submodule()
