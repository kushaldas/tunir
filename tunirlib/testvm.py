# -*- coding: utf-8 -*-
# Copyright 2014, Red Hat, Inc.
# License: GPL-2.0+ <http://spdx.org/licenses/GPL-2.0+>
# See the LICENSE file for more details on Licensing

"""
This is a module for downloading fedora cloud images (and probably any other
qcow2) and then booting them locally with qemu.
"""

import os
import glob
import subprocess
import sys
import urllib2
import shutil

import config


def koji_download(urls, download_path):
    """ Downloads files (qcow2s, specifically) from a list of URLs with an
    optional progress bar. Returns a list of raw image files. """

    # This code was blatantly stolen from fedimg - but it was depreciated,
    # that's the internet version of sitting in front of someone's house with
    # a sign saying "FREE." Thanks oddshocks!

    # Create the proper local upload directory

    print "Local downloads will be stored in {}.".format(
        download_path)

    # When qcow2s are downloaded and converted, they are added here
    raw_files = list()

    for url in urls:
        file_name = url.split('/')[-1]
        local_file_name = os.path.join(download_path, file_name)
        u = urllib2.urlopen(url)
        try:
            with open(local_file_name, 'wb') as f:
                meta = u.info()
                file_size = int(meta.getheaders("Content-Length")[0])

                print "Downloading {0} ({1} bytes)".format(url, file_size)
                bytes_downloaded = 0
                block_size = 8192

                while True:
                    buff = u.read(block_size)  # buffer
                    if not buff:

                        raw_files.append(local_file_name)

                        print "Succeeded at downloading {}".format(file_name)
                        break

                    bytes_downloaded += len(buff)
                    f.write(buff)
                    bytes_remaining = float(bytes_downloaded) / file_size
                    if config.DOWNLOAD_PROGRESS:
                        # TODO: Improve this progress indicator by making
                        # it more readable and user-friendly.
                        status = r"{0} [{1:.2%}]".format(bytes_downloaded,
                                                         bytes_remaining)
                        status = status + chr(8) * (len(status) + 1)
                        sys.stdout.write(status)

            return raw_files

        except OSError:
            print "Problem writing to {}.".format(config.LOCAL_DOWNLOAD_DIR)


def expand_qcow(image, size="+10G"):
    """Expand the storage for a qcow image. Currently only used for Atomic
    Hosts."""

    subprocess.call(['qemu-img',
                     'resize',
                     image,
                     size])

    print "Resized image for Atomic testing..."
    return


def create_user_data(path, password, overwrite=False, atomic=False):
    """Save the right  password to the 'user-data' file needed to
    emulate cloud-init. Default username on cloud images is "fedora"

    Will not overwrite an existing user-data file unless
    the overwrite kwarg is set to True."""

    if atomic:
        file_data = config.ATOMIC_USER_DATA % password

    else:
        file_data = config.USER_DATA % password

    if os.path.isfile(path + '/meta/user-data'):
        if overwrite:

            with open(path + '/meta/user-data', 'w') as user_file:
                user_file.write(file_data)

                return "user-data file generated."
        else:
            return "user-data file already exists"

    with open(path + '/meta/user-data', 'w') as user_file:
        user_file.write(file_data)

    return "user-data file generated."


def create_meta_data(path, hostname, overwrite=False):
    """Save the required hostname data to the 'meta-data' file needed to
    emulate cloud-init.

    Will not overwrite an existing user-data file unless
    the overwrite kwarg is set to True."""

    file_data = config.META_DATA % hostname

    if os.path.isfile(path + '/meta/meta-data'):
        if overwrite:

            with open(path + '/meta/meta-data', 'w') as meta_data_file:
                meta_data_file.write(file_data)

                return "meta-data file generated."
        else:
            return "meta-data file already exists"

    with open(path + '/meta/meta-data', 'w') as meta_data_file:
        meta_data_file.write(file_data)

    return "meta-data file generated."


def create_seed_img(meta_path, img_path):
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


def download_initrd_and_kernel(qcow2_image, path):
    """Download the necessary kernal and initrd for booting a specified cloud
    image. Returns a dict {'kernel': '', 'initrd': ''} after the download
    is completed."""

    subprocess.call(['virt-builder', '--get-kernel', qcow2_image], cwd=path)

    result = {}

    try:
        result['kernel'] = glob.glob("%s/*vmlinuz*" % path)[0]
        result['initrd'] = glob.glob("%s/*initramfs*" % path)[0]

    except IndexError:
        print "Unable to find kernel or initrd, did they download?"
        return

    return result


def boot_image(
        qcow2, seed, initrd=None, kernel=None, ram=1024, graphics=False,
        vnc=False, atomic=False, port=''):
    """Boot the cloud image redirecting local port 8888 to 80 on the vm as
    well as local port 2222 to 22 on the vm so http and ssh can be accessed."""

    boot_args = ['/usr/bin/qemu-kvm',
                 '-m',
                 str(ram),
                 '-drive',
                 'file=%s,if=virtio' % qcow2,
                 '-drive',
                 'file=%s,if=virtio' % seed,
                 '-redir',
                 'tcp:%s::22' % port,
                 ]

    if not atomic:
        boot_args.extend(['-kernel',
                          '%s' % kernel,
                          '-initrd',
                          '%s' % initrd,
                          '-append',
                          'root=/dev/vda1 ro ds=nocloud-net'
                          ])

    if graphics:
        boot_args.extend(['-nographic'])

    if vnc:
        boot_args.extend(['-vnc', '0.0.0.0:1'])

    print ' '.join(boot_args)
    vm = subprocess.Popen(boot_args)

    print "Successfully booted your local cloud image!"
    print "PID: %d" % vm.pid

    return vm


def build_and_run(
        image_url, ram=1024, graphics=False, vnc=False, atomic=False, port='', image_dir='/tmp'):
    """Run through all the steps."""

    print "cleaning and creating dirs..."
    clean_dirs()
    create_dirs()

    base_path = image_dir

    # Create cloud-init data
    print "Creating meta-data..."
    create_user_data(base_path, "passw0rd", atomic=atomic)
    create_meta_data(base_path, "testCloud")

    create_seed_img(base_path + '/meta', base_path)

    # Download image and get kernel/initrd

    image_file = os.path.join(base_path, image_url.split('/')[-1])

    if not os.path.isfile(image_file):
        print "downloading new image..."
        image = koji_download([image_url], image_dir)[0]

        if atomic:
                expand_qcow(image)
    else:
        print "using existing image..."
        image = image_file

    if not atomic:
        external = download_initrd_and_kernel(image, base_path)

    if atomic:
        vm = boot_image(image,
                        base_path + '/seed.img',
                        ram=ram,
                        graphics=graphics,
                        vnc=vnc,
                        atomic=atomic,
                        port=port)
    else:
        vm = boot_image(image,
                        base_path + '/seed.img',
                        external['initrd'],
                        external['kernel'],
                        ram=ram,
                        graphics=graphics,
                        vnc=vnc,
                        port=port)

    return vm


def create_dirs():
    """Create the dirs in /tmp that we need to store things."""
    os.makedirs('/tmp/testCloud/meta')
    return "Created tmp directories."


def clean_dirs():
    """Remove dirs after a test run."""
    if os.path.exists('/tmp/testCloud'):
        shutil.rmtree('/tmp/testCloud')
    return "All cleaned up!"


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url",
                        help="URL to qcow2 image is required.",
                        type=str)
    parser.add_argument("--ram",
                        help="Specify the amount of ram for the VM.",
                        type=int,
                        default=512)
    parser.add_argument("--no-graphic",
                        help="Turn off graphical display.",
                        action="store_true")
    parser.add_argument("--vnc",
                        help="Turns on vnc at :1 to the instance.",
                        action="store_true")
    parser.add_argument("--atomic",
                        help="Use this flag if you're booting an Atomic Host.",
                        action="store_true")

    args = parser.parse_args()

    gfx = False
    vnc = False
    atomic = False

    if args.no_graphic:
        gfx = True

    if args.vnc:
        vnc = True

    if args.atomic:
        atomic = True

    build_and_run(args.url, args.ram, graphics=gfx, vnc=vnc, atomic=atomic)

if __name__ == '__main__':
    main()
