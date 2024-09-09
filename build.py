#!/usr/bin/env python3

import argparse
import io
import git
import multiprocessing
import re
import shutil
import subprocess

from enum import Enum, auto
from git import Repo
from pathlib import Path
from tarfile import TarFile
from typing import TypedDict, Required, NotRequired

class MtkFilogic(Enum):
    MT7981A = auto()
    MT7981B = auto()
    MT7986A = auto()
    MT7986B = auto()
    MT7988 = auto()
    MT7988D = auto()

class MemoryChipType(Enum):
    DDR = auto()
    DDR2 = auto()
    DDR3 = auto()
    LPDDR3 = auto()
    DDR4 = auto()
    LPDDR4 = auto()

class StorageChipType(Enum):
    NOR = auto()
    NAND = auto()
    SPI_NAND = auto()
    EMMC = auto()

class RouterMachine(TypedDict):
    name: Required[str]
    description: NotRequired[str]
    soc: Required[MtkFilogic]
    ram: Required[MemoryChipType]
    storage: Required[StorageChipType]
    defconfig: NotRequired[str]

def check_build_directory(sub_mod: git.objects.submodule.base.Submodule):
    mod_name = sub_mod.name
    build_dir = 'build-{0}'.format(mod_name)
    unpack_stamp_file = Path(build_dir) / '.unpack_checked'

    if unpack_stamp_file.is_file():
        print("{0} build directory exists".format(mod_name))
        return

    with io.BytesIO() as tardata:
        with Repo(sub_mod) as repo:
            repo.archive(tardata)
        tardata.seek(0)
        with TarFile(fileobj=tardata) as tmp_tar:
            tmp_tar.extractall(path=build_dir, filter='tar')
            unpack_stamp_file.touch(exist_ok=False)
            return

def prepare_submodule():
    repo = Repo()
    sms = repo.submodules

    [check_build_directory(sm) for sm in sms]

def copy_quilt_files_to_build(sub_mod: git.objects.submodule.base.Submodule):
    mod_name = sub_mod.name
    build_dir = Path('build-{0}'.format(mod_name))
    unpack_stamp_file = Path(build_dir) / '.unpack_checked'
    quilt_prepare_stamp_file = Path(build_dir) / '.quilt_checked'

    if quilt_prepare_stamp_file.is_file():
        print("{0} has been prepared".format(build_dir))
        return

    if not unpack_stamp_file.is_file():
        print("{0} didn't unpack by us".format(build_dir))
        return

    dst_dir = build_dir / 'patches'
    patch_dir = '{0}-patches'.format(mod_name)
    shutil.copytree(patch_dir, dst_dir)

    # match patch and diff files
    patches_list = sorted(dst_dir.glob('*.[pd][ai][tf][cf]*'))

    with open(dst_dir / 'series', 'w') as series_file:
        [print(p.name, file=series_file) for p in patches_list]

    quilt_prepare_stamp_file.touch(exist_ok=False)

def apply_patches_in_build(sub_mod: git.objects.submodule.base.Submodule):
    mod_name = sub_mod.name
    build_dir = Path('build-{0}'.format(mod_name))

    quilt_prepare_stamp_file = Path(build_dir) / '.quilt_checked'
    if not quilt_prepare_stamp_file.is_file():
        print("{0} is not prepared by us".format(build_dir))
        return

    quilt_path = shutil.which('quilt')
    quilt_applied_stamp_file = Path(build_dir) / '.quilt_applied_checked'

    if quilt_applied_stamp_file.is_file():
        print("The patch has been applied for {0}".format(mod_name))
        return

    with subprocess.Popen([quilt_path, '--quiltrc=-','push', '-a'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=build_dir, text=True) as proc:
        try:
            outs, errs = proc.communicate(timeout=5)
            if errs:
                print('apply patches for {} error:'.format(mod_name))
                print(errs)
                return
            quilt_applied_stamp_file.touch(exist_ok=False)
        except TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate()


def copy_and_apply_patches():
    repo = Repo()
    sms = repo.submodules

    [(copy_quilt_files_to_build(sm), apply_patches_in_build(sm)) for sm in sms]

def configura_uboot(defconfig : str):
    build_dir = Path('build-u-boot')

    configed_stamp_file = Path(build_dir) / '.config_checked'
    try:
        subprocess.run(['make', '-C', str(build_dir.absolute()), defconfig],
                       check=True, capture_output=True)
        configed_stamp_file.touch(exist_ok=True)
    except subprocess.CalledProcessError:
        configed_stamp_file.unlink()

def write_atf_config_file(machine: RouterMachine, boot_to_ram: bool):
    build_dir = Path('build-atf')
    sub_build_dir = build_dir / 'build'
    sub_build_dir.mkdir(exist_ok=True)

    with open(sub_build_dir / '.config', 'w') as file:
        soc_name = re.findall(r'MT\d{,4}', machine['soc'].name)
        if len(soc_name) > 0:
            print('_PLAT_{}=y'.format(soc_name[0]), file=file)

        print('_DRAM_{}=y'.format(machine['ram'].name), file=file)
        if boot_to_ram:
            print('_BOOT_DEVICE_RAM=y', file=file)
        else:
            print('_BOOT_DEVICE_{}=y'.format(machine['storage'].name), file=file)

        print('_ENABLE_I2C_SUPPORT=y', file=file)
        print('_ENABLE_EMERG_MEM_DUMP=y', file=file)
        print('_ENABLE_JTAG=y', file=file)
        print('_BUILD_FIP=n', file=file)

    configed_stamp_file = Path(build_dir) / '.config_checked'
    try:
        subprocess.run(['make', '-C', str(build_dir.absolute()), 'defconfig'],
                       check=True, capture_output=True)
        configed_stamp_file.touch(exist_ok=True)
    except subprocess.CalledProcessError:
        configed_stamp_file.unlink()

def build_uboot(crossprefix : str):
    build_dir = Path('build-u-boot')

    built_stamp_file = Path(build_dir) / '.built_checked'
    n_threads = multiprocessing.cpu_count()
    try:
        subprocess.run(['make', '-C', str(build_dir.absolute()), '-j', str(n_threads),
                        'CROSS_COMPILE={}'.format(crossprefix)],
                       check=True, capture_output=True)
        built_stamp_file.touch(exist_ok=True)
    except subprocess.CalledProcessError:
        built_stamp_file.unlink()

def build_atf(crossprefix : str):
    build_dir = Path('build-atf')

    built_stamp_file = Path(build_dir) / '.built_checked'
    n_threads = multiprocessing.cpu_count()
    try:
        subprocess.run(['make', '-C', str(build_dir.absolute()), '-j', str(n_threads),
                        'CROSS_COMPILE={}'.format(crossprefix)],
                       check=True, capture_output=True)
        built_stamp_file.touch(exist_ok=True)
    except CalledProcessError:
        built_stamp_file.unlink()

if __name__ == '__main__':
    machines : list[RouterMachine] = [ \
            {'name': 'jdcloud-re-cp-03', 'description': 'JD Cloud Bali AX6000',
             'soc': MtkFilogic.MT7986A, 'ram': MemoryChipType.DDR4,
             'storage': StorageChipType.EMMC,
             'defconfig': 'mt7986a_jdcloud_re-cp-03_defconfig'},
            ]

    machines_choices = [d['name'] for d in machines]

    targets = ['all', 'atf', 'u-boot']

    parser = argparse.ArgumentParser(prog='build.py')
    subparsers = parser.add_subparsers(dest='step')

    subparsers.add_parser('unpack', help='prepare the build directory')
    subparsers.add_parser('patch', help='patch source codes')

    parser_config = subparsers.add_parser('config')
    parser_config.add_argument('machine', choices=machines_choices)
    parser_config.add_argument('--ram', dest='boot_to_ram', action='store_true')

    parser_build = subparsers.add_parser('build')
    parser_build.add_argument('target', choices=targets)
    parser_build.add_argument('--cross', dest='crossprefix', default='aarch64-linux-gnu-')

    subparsers.add_parser('firmware', help='packing the firmware')

    args = parser.parse_args()

    match args.step:
        case 'unpack':
            prepare_submodule()
        case 'patch':
            copy_and_apply_patches()
        case 'config':
            try:
                index = machines_choices.index(args.machine)
            except ValueError:
                print("can't find machine {}".format(args.machine))
                exit(1)

            machine = machines[index]
            write_atf_config_file(machine, args.boot_to_ram)
            configura_uboot(machine['defconfig'])
        case 'build':
            match args.target:
                case 'all':
                    build_uboot(args.crossprefix)
                    build_atf(args.crossprefix)
                case 'atf':
                    build_atf(args.crossprefix)
                case 'u-boot':
                    build_uboot(args.crossprefix)
