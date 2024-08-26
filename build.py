#!/usr/bin/env python3

import argparse
import io
import git
import shutil
import subprocess

from git import Repo
from pathlib import Path
from tarfile import TarFile

def check_build_directory(sub_mod: git.objects.submodule.base.Submodule):
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

def copy_quilt_files_to_build(sub_mod: git.objects.submodule.base.Submodule):
    mod_name = sub_mod.name
    build_dir = Path('build-{0}'.format(mod_name))
    dst_dir = build_dir / 'patches'
    patch_dir = '{0}-patches'.format(mod_name)
    shutil.copytree(patch_dir, dst_dir)

def copy_and_apply_patches():
    repo = Repo()
    sms = repo.submodules

    [copy_quilt_files_to_build(sm) for sm in sms]

if __name__ == '__main__':
    targets = ['all', 'atf', 'u-boot']
    machines = [ \
            {'name': 'jdcloud-re-cp-03', 'description': 'JD Cloud Bali AX6000',
             'soc': 'MT7986', 'ram': 'DDR4', 'sotarge': 'EMMC',
             'dts': 'mt7986a-jdcloud_re-cp-03'},
            ]

    machines_choices = [d['name'] for d in machines]

    parser = argparse.ArgumentParser(prog='build.py')
    subparsers = parser.add_subparsers(dest='step')

    subparsers.add_parser('unpack', help='prepare the build directory')
    subparsers.add_parser('patch', help='patch source codes')

    parser_config = subparsers.add_parser('config')
    parser_config.add_argument('machine', choices=machines_choices)
    parser_config.add_argument('--ram', dest='boot_to_ram', action='store_true')

    parser_build = subparsers.add_parser('build')
    parser_build.add_argument('target', choices=targets)

    subparsers.add_parser('firmware', help='packing the firmware')

    args = parser.parse_args()

    match args.step:
        case 'unpack':
            prepare_submodule()
        case 'patch':
            copy_and_apply_patches()
