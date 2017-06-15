# -*- coding: utf-8 -*-
# Copyright 2014, Red Hat, Inc.
# License: GPL-2.0+ <http://spdx.org/licenses/GPL-2.0+>
# See the LICENSE file for more details on Licensing

"""
This is a module for downloading fedora cloud images (and probably any other
qcow2) and then booting them locally with qemu.
"""

import subprocess
from .config import USER_DATA


def create_user_data(path, password):
    # type: (str, str) -> str
    "Creates a simple user data file"
    file_data = USER_DATA % password
    with open(path + '/meta/user-data', 'w') as user_file:
        user_file.write(file_data)
    return "user-data file generated."


def create_seed_img(meta_path, img_path):
    # type: (str, str) -> str
    """Create a virtual filesystem needed for boot with virt-make-fs on a given
    path (it should probably be somewhere in '/tmp'."""

    make_image = subprocess.call(['virt-make-fs',
                                  '--type=msdos',
                                  '--label=cidata',
                                  meta_path,
                                  img_path + '/seed.img'])

    if make_image == 0:
        return "seed.img created at %s" % img_path

    return "creation of the seed.img failed."
