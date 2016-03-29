# -*- coding: utf-8 -*-
"Tunir module to talk to Vagrant"

# Copyright © 2015-2016  Kushal Das <kushaldas@gmail.com>
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2, or (at your option) any later
# version.  This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.  You
# should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

import os
import time
import subprocess


def system(cmd):
    """
    Runs a shell command, and returns the output, err, returncode

    :param cmd: The command to run.
    :return:  Tuple with (output, err, returncode).
    """
    ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    out, err = ret.communicate()
    returncode = ret.returncode
    return out, err, returncode

def refresh_vol_pool():
    '''Refreshes libvirt volume by removing extra files..

    '''
    out, err, retcode = system('virsh vol-list default')
    lines = out.split('\n')
    if len(lines) > 2:
        for line in lines[2:]:
            words = line.split()
            if len(words) == 2:
                if words[0].startswith('tunir-box'):
                    system('virsh vol-delete {0} default'.format(words[0]))

def refresh_storage_pool():
    '''Refreshes libvirt storage pool.

    http://kushaldas.in/posts/storage-volume-error-in-libvirt-with-vagrant.html
    '''
    out, err, retcode = system('virsh pool-list')
    lines = out.split('\n')
    if len(lines) > 2:
        for line in lines[2:]:
            words = line.split()
            if len(words) == 3:
                if words[1] == 'active':
                    system('virsh pool-refresh {0}'.format(words[0]))


def parse_ssh_config(text):
    """
    Parses the SSH config and returns a dict
    """
    result = {}
    lines = text.split('\n')
    if lines[0].strip().startswith('Host '):
        for line in lines[1:]:
            line = line.strip()
            words = line.split(' ')
            if len(words) == 2:
                result[words[0]] = words[1]

    return result


class Vagrant(object):
    """
    Returns a Vagrant object.
    """
    def __init__(self, image_url, name='tunir-box', memory=1024, provider='libvirt', path='/var/run/tunir/'):
        self.original_path = os.path.abspath(os.path.curdir)
        self.name = name
        self.image_url = image_url
        self.path = path
        self.keys = None
        self.failed = False
        self.provider = provider

        libvirt_config = '''Vagrant.configure("2") do |config|
  config.vm.define :tunirserver do |tunirserver|
    tunirserver.vm.box = "{0}"
    tunirserver.vm.provider :libvirt do |domain|
      domain.memory = {1}
      domain.cpus = 2
    end
  end
end'''

        virtualbox_config = '''Vagrant.configure("2") do |config|
  config.vm.box = "{0}"
  config.vm.synced_folder ".", "/home/vagrant/sync", disabled: true
  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.provider :virtualbox do |domain|
      domain.memory = {1}
      domain.cpus = 2
  end
end'''

        self.vagrantfile = None
        if self.provider == 'libvirt':
            self.vagrantfile = libvirt_config
            refresh_storage_pool()
        else:
            self.vagrantfile = virtualbox_config
        os.chdir(self.path)

        with open('Vagrantfile', 'w') as fobj:
            fobj.write(self.vagrantfile.format(name, memory))

        print "Wrote Vagrant config file."
        # Now actually register that image

        basename = os.path.basename(image_url)


        print "Adding vagrant box."
        cmd = 'vagrant box add {0} --name {1}'.format(image_url, name)
        out, err, retcode = system(cmd)
        # Now check for error, I will skip this.
        if retcode != 0:
            print("Error while trying to add the box.")
            print err
            self.failed = True
            return
        print out

        print "Up the vagrant"

        # Let us up the vagrant
        cmd = 'vagrant up --provider {0}'.format(self.provider)
        out, err, retcode = system(cmd)
        if retcode != 0:
            print("Error while trying to do vagrant up the box.")
            print err
            self.failed = True
            return
        print out

        time.sleep(3)
        print "Time to get Vagrant ssh-config"


        # Now let us try to get the ssh-config
        cmd = 'vagrant ssh-config'
        out, err, retcode = system(cmd)
        if retcode != 0:
            print("Error while trying to get ssh config for the box.")
            print err
            self.failed = True
            return
        print out
        self.keys = parse_ssh_config(out)
        os.chdir(self.original_path)

    def destroy(self):
        os.chdir(self.path)
        print "Let us destroy the box."
        cmd = 'vagrant destroy -f'
        out, err, retcode = system(cmd)
        if retcode != 0:
            print("Error while trying to destroy the instance.")
            print err

        cmd = 'vagrant box remove {0} -f'.format(self.name)
        out, err, retcode = system(cmd)
        if retcode != 0:
            print("Error while trying to remove the box.")
            print err

        if self.provider == 'libvirt':
            refresh_vol_pool() # Remove libvirt cache
        os.chdir(self.original_path)

def vagrant_and_run(config, path='/var/run/tunir/'):
    """
    This starts the vagrant box

    :param config: Our config object
    :return: (Vagrant, config) config object with IP, and key file
    """
    v = Vagrant(config['image'], memory=config['ram'],
                provider=config.get('provider', 'libvirt'), path=path)
    if v.keys: # Means we have the box up, and also the ssh config
        config['host_string'] = v.keys['HostName']
        config['ip'] = v.keys['HostName']
        config['key'] = v.keys['IdentityFile'].strip('"')
        config['port'] = v.keys['Port']

    return v, config




if __name__ == '__main__':
    data = '''Host default
  HostName 192.168.121.18
  User vagrant
  Port 22
  UserKnownHostsFile /dev/null
  StrictHostKeyChecking no
  PasswordAuthentication no
  IdentityFile /root/vg/.vagrant/machines/default/libvirt/private_key
  IdentitiesOnly yes
  LogLevel FATAL
'''
    print parse_ssh_config(data)

