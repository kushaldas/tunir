import os
import sys
import time
import signal
import random

from io import StringIO
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from paramiko.rsakey import RSAKey
import subprocess
import tempfile
from typing import Tuple, Dict

import configparser as ConfigParser
import logging
from pprint import pprint
from .tunirutils import run, clean_tmp_dirs, system, run_job
from .tunirutils import match_vm_numbers, create_ansible_inventory
from .tunirutils import IPException
from .testvm import  create_user_data, create_seed_img
log = logging.getLogger('tunir')

def true_test(vms, private_key, command='cat /proc/cpuinfo'):
    """
    Runs a given command to the list of vms. Currently using it
    to push the list of vms/ips to the /etc/hosts files.

    :param vms: Dictionary of the VM(s) with ip addresses to work on
    :param private_key: String version of the private key to ssh
    :param command: The actual command to run.
    :return: None
    """
    "Just to test the connection of a vm"
    key = create_rsa_key(private_key)
    for vm in vms.values():
        for i in range(5):
            try:
                res = run(vm['ip'], port=vm['port'], user=vm['user'], command=command,pkey=key, debug=False)
                break
            except Exception as e:
                print("Try {0} failed for IP injection to /etc/hosts.".format(i))
                if i == 4: # If it does not allow in 2 minutes, something is super wrong
                    raise e
                time.sleep(30)
                continue

def inject_ip_to_vms(vms, private_key):
    """
    Updates each vm's /etc/hosts file with IP addresses.

    :param vms: Dictionary of VM(s)/IPs
    :param private_key: String version of the private key
    :return: None
    """

    text = "\n"
    for k, v in vms.items():
        line = ''
        # ip hostname format for /etc/hosts
        if 'hostname' in v:
            line = "{0}    {1} {2}\n".format(v['ip'],k,v['hostname'])
        else:
            line = "{0}    {1}\n".format(v['ip'],k)
        text += line
    true_test(vms, private_key, """sudo sh -c 'echo -e "{0}" >> /etc/hosts'""".format(text))


def create_rsa_key(private_key: str) -> RSAKey:
    """ Creates the RSAKey for paramiko.
    :param private_key: String version of the private key
    :return: The RSAKey object to be used in paramiko
    """

    fobj = StringIO(private_key)
    key = RSAKey.from_private_key(fobj)
    return key


def generate_sshkey(bits: int=2048) -> Tuple[str,str] :
    '''
    Returns private key and public key
    '''
    key = rsa.generate_private_key(backend=default_backend(), public_exponent=65537, \
                                   key_size=bits)

    # OpenSSH format public key
    pkey = key.public_key().public_bytes(serialization.Encoding.OpenSSH, \
                                               serialization.PublicFormat.OpenSSH)

    # PEM format private key
    pem = key.private_bytes(encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.TraditionalOpenSSL,
                            encryption_algorithm=serialization.NoEncryption())
    private_key = pem.decode('utf-8')
    public_key = pkey.decode('utf-8')
    return private_key, public_key

def scan_arp(macaddr):
    "Find the ip for the given mac addr"
    output, err, eid = system('arp -an')
    lines = output.split('\n')
    for line in lines:
        words = line.split(' ')
        if len(words) > 3:
            if words[3].strip() == macaddr:
                return words[1].strip('()')

def read_multihost_config(filepath):
    '''Reads the given filepath, and returns a dict with all required information.
    '''
    result = {}
    config = ConfigParser.RawConfigParser()
    config.read(filepath)
    sections = config.sections()
    for sec in sections:
        items = config.items(sec)
        out = dict(items)
        result[sec] = out
    return result

def random_mac():
    """
    Generates a random MAC address
    :return: A string containing the random MAC address.
    """
    mac = [ 0x00, 0x16, 0x3e,\
        random.randint(0x00, 0x7f),\
        random.randint(0x00, 0xff),\
        random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

def boot_qcow2(image, seed, ram=1024, vcpu='1'):
    "Boots the image with a seed image"
    mac = random_mac()
    boot_args = ['/usr/bin/qemu-kvm',
                 '-m',
                 str(ram),
                 '-smp',
                 vcpu,
                 '-drive',
                 'file=%s,if=virtio' % image,
                 '-drive',
                 'file=%s,if=virtio' % seed,
                 '-net',
                 'bridge,br=virbr0',
                 '-net',
                 'nic,macaddr={0},model=virtio'.format(mac),
                 '-device', 'virtio-rng-pci', # https://bugzilla.redhat.com/show_bug.cgi?id=1212082
                 '-display',
                 'none'
                 ]
    print(' '.join(boot_args))
    vm = subprocess.Popen(boot_args)

    print("Successfully booted your local cloud image!")

    return vm, mac

def create_ssh_metadata(path, pub_key, private_key=None):
    "Creates the user data with ssh key"
    text = """instance-id: iid-123456
local-hostname: tunirtests
public-keys:
  default: {0}
"""
    fname = os.path.join(path, 'meta/meta-data')
    with open(fname, 'w') as fobj:
        fobj.write(text.format(pub_key))

    # just for debugging
    if private_key:
        pname = os.path.join(path, 'private.pem')
        with open(pname,'w') as fobj:
            fobj.write(private_key)
        os.system('chmod 0600 {0}'.format(pname))

def start_multihost(jobname, jobpath, debug=False, oldconfig=None, config_dir='.'):
    "Start the executation here."
    temppath = tempfile.mktemp()
    extra_config = {'result_path' : temppath}
    print('Result file at: {0}'.format(temppath))
    status = 0
    ansible_inventory_path = None
    fault_in_ip_addr = False
    private_key = None
    config_path = os.path.join(config_dir, jobname + '.cfg')
    if debug:
        print(config_path)
    config = None
    vcpu = '2'
    vms = {} # Empty directory to store vm details
    dirs_to_delete = [] # We will delete those at the end
    vm_keys = None
    if not oldconfig:
        config = read_multihost_config(config_path)
        ram = config.get('general').get('ram', '1024')
        vcpu = config.get('general').get('cpu', '1')
        result_path = config.get('general').get('result_path', None)
        if result_path:
            extra_config['result_path'] = result_path
        vm_keys = [name for name in config.keys() if name.startswith('vm')]
        if 'key' in config['general']:
            data = ''
            try:
                with open(config['general']['key']) as fobj:
                    data = fobj.read()
            except Exception as e:
                print(e)
                raise e
            config['general']['pkey'] = create_rsa_key(data)
            private_key = data
            config['general']['keypath'] = config['general']['key']
    else: # For a single vm job or Vagrant or AWS
        config = {'vm1': oldconfig}
        config['general'] = {'ansible_dir': oldconfig.get('ansible_dir', None)}
        if 'key' in oldconfig:
            data = ''
            with open(oldconfig['key']) as fobj:
                data = fobj.read()
            config['general']['pkey'] = create_rsa_key(data)
            config['general']['keypath'] = oldconfig['key']
            private_key = data
            config['general']['key'] = data
        ram = oldconfig.get('ram', '1024')
        vm_keys = ['vm1',]
    #TODO Parse the job file first
    if not os.path.exists(jobpath):
        print("Missing job file {0}".format(jobpath))
        return False

    # For extra vm(s) in the job file fail fast
    if not match_vm_numbers(vm_keys, jobpath):
        return

    # First let us create the seed image
    seed_dir = tempfile.mkdtemp()
    print('Created {0}'.format(seed_dir))
    os.system('chmod 0777 %s' % seed_dir)
    dirs_to_delete.append(seed_dir)
    if 'key' not in config['general']:
        # Then we create key and metadata
        meta = os.path.join(seed_dir, 'meta')
        os.makedirs(meta)
        print("Generating SSH keys")
        private_key, public_key = generate_sshkey()
        create_user_data(seed_dir, "passw0rd")
        create_ssh_metadata(seed_dir, public_key, private_key)
        create_seed_img(meta, seed_dir)
        seed_image = os.path.join(seed_dir, 'seed.img')

        # We will copy the seed in every vm run dir
        pkey = create_rsa_key(private_key)

    try:
        for vm_c in vm_keys:
            # Now create each vm one by one.
            # Get the current ips
            this_vm = {}
            if 'ip' not in config[vm_c]:
                current_d = tempfile.mkdtemp()
                print('Created {0}'.format(current_d))
                os.system('chmod 0777 %s' % current_d)
                dirs_to_delete.append(current_d)
                system('cp  {0} {1}'.format(seed_image, current_d))
                # Next copy the qcow2 image
                image_path = config[vm_c].get('image')
                os.system('cp {0} {1}'.format(image_path, current_d))
                image = os.path.join(current_d, os.path.basename(image_path))
                log.info("Booting {0}".format(image))

                vm, mac = boot_qcow2(image, os.path.join(current_d, 'seed.img'), ram, vcpu=vcpu)
                this_vm.update({'process': vm, 'mac': mac})
                # Let us get this vm in the tobe delete list even if the IP never comes up
                vms[vm_c] = this_vm
                print("We will wait for 45 seconds for the image to boot up.")
                time.sleep(45)
                latest_ip = scan_arp(mac)
                if not latest_ip:
                    fault_in_ip_addr = True
                    break
                this_vm['ip'] = latest_ip
                this_vm['host_string'] = latest_ip
                this_vm['pkey'] = pkey
                this_vm['port'] = config[vm_c].get('port', 22)
            else:
                this_vm['ip'] = config[vm_c].get('ip')
                this_vm['host_string'] = config[vm_c].get('ip')
                this_vm['port'] = config[vm_c].get('port', 22)
                this_vm['pkey'] = config['general']['pkey']

            this_vm['user'] = config[vm_c].get('user')
            if 'hostname' in config[vm_c]:
                this_vm['hostname'] = config[vm_c].get('hostname')
            log.info("IP of the new instance: {0}".format(this_vm.get('ip')))

            vms[vm_c] = this_vm
        only_vms = vms.copy()
        vms['general'] = config['general']
        if fault_in_ip_addr:
            print('Oops no IP for this vm.')
            raise IPException

        # Now we are supposed to have all the vms booted.
        if debug:
            pprint(vms)
        print(' ')
        inject_ip_to_vms(only_vms, private_key)
        ansible_flag = config.get('general').get('ansible_dir', None)
        if ansible_flag:
            dir_to_copy = ansible_flag
            if not dir_to_copy.endswith('/'):
                dir_to_copy += '/*'
            else:
                dir_to_copy += '*'
            os.system('cp -r {0} {1}'.format(dir_to_copy, seed_dir))
            ansible_inventory_path = os.path.join(seed_dir, 'tunir_ansible')
            create_ansible_inventory(only_vms, ansible_inventory_path)


        # This is where we test
        status = run_job(jobpath,job_name=jobname,vms=vms, ansible_path=seed_dir, extra_config=extra_config)
    except Exception as e:
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("*** print_tb:")
        traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        print("*** print_exception:")
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                              limit=2, file=sys.stdout)

    finally:
        if debug:
            filename = os.path.join(seed_dir, 'destroy.sh')
            with open(filename, 'w') as fobj:
                for vm in only_vms.values():
                    if not 'process' in vm: # For remote vm/bare metal
                        continue
                    job_pid = vm['process'].pid
                    fobj.write('kill -9 {0}\n'.format(job_pid))
                for d in dirs_to_delete:
                    fobj.write('rm -rf {0}\n'.format(d))
            print("DEBUG MODE ON. Destroy from {0}".format(filename))
            # Put the ip/hostnames into a text file
            filename = os.path.join(seed_dir, 'hostnames.txt')
            with open(filename, 'w') as fobj:
                for k, v in only_vms.items():
                    fobj.write('{0}={1}\n'.format(k,v['ip']))
            return status # Do not destroy for debug case
        for vm in only_vms.values():
            if not 'process' in vm: # For remote vm/bare metal
                continue
            job_pid = vm['process'].pid
            if debug:
                print('Killing {0}'.format(job_pid))
            os.kill(job_pid, signal.SIGKILL)
        clean_tmp_dirs(dirs_to_delete)
        return status
