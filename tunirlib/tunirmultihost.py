import os
import time
import signal
import random
import cStringIO
from Crypto.PublicKey import RSA
from paramiko.rsakey import RSAKey
import subprocess
import tempfile
import ConfigParser
from pprint import pprint
from .tunirutils import run, clean_tmp_dirs, system, run_job
from .tunirutils import match_vm_numbers, create_ansible_inventory
from .testvm import  create_user_data, create_seed_img

def true_test(vms, private_key, command='cat /proc/cpuinfo'):
    "Just to test the connection of a vm"
    fobj = cStringIO.StringIO(private_key)
    key = RSAKey(file_obj=fobj)
    for vm in vms.values():
        res = run(vm['ip'],22,user=vm['user'], command=command,pkey=key, debug=False)

def inject_ip_to_vms(vms, private_key):
    "Updates each vm's /etc/hosts file with IP addresses"
    text = "\n"
    for k, v in vms.iteritems():
        line = ''
        # ip hostname format for /etc/hosts
        if 'hostname' in v:
            line = "{0}    {1} {2}\n".format(v['ip'],k,v['hostname'])
        else:
            line = "{0}    {1}\n".format(v['ip'],k)
        text += line
    true_test(vms, private_key, """sudo sh -c 'echo -e "{0}" >> /etc/hosts'""".format(text))

def create_rsa_key(private_key):
    fobj = cStringIO.StringIO(private_key)
    key = RSAKey(file_obj=fobj)
    return key

def generate_sshkey(bits=2048):
    '''
    Returns private key and public key, and the key object
    '''
    key = RSA.generate(bits, e=65537)
    public_key = key.publickey().exportKey("OpenSSH")
    private_key = key.exportKey("PEM")
    return private_key, public_key, key

def scan_nmap():
    """Finds all the ips from the nmap -sn 192.168.122.* output.
    :returns: List of ips
    """
    print('Scanning ips.')
    output, err, eid = system('nmap -sn 192.168.122.*')
    lines = output.split('\n')
    ips = []
    for line in lines:
        if line.startswith('Nmap scan report for'):
            ip = line.split(' ')[-1]
            ips.append(ip)
    return ips

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
    mac = [ 0x00, 0x16, 0x3e,\
        random.randint(0x00, 0x7f),\
        random.randint(0x00, 0xff),\
        random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

def boot_qcow2(image, seed, ram=1024, vcpu=1):
    "Boots the image with a seed image"
    mac = random_mac()
    boot_args = ['/usr/bin/qemu-kvm',
                 '-m',
                 str(ram),
                 '-drive',
                 'file=%s,if=virtio' % image,
                 '-drive',
                 'file=%s,if=virtio' % seed,
                 '-net',
                 'bridge,br=virbr0',
                 '-net',
                 'nic,macaddr={0},model=virtio'.format(mac),
                 '-nographic'
                 ]
    print(' '.join(boot_args))
    vm = subprocess.Popen(boot_args)

    print "Successfully booted your local cloud image!"
    print "PID: %d" % vm.pid

    return vm

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

    # just for testing
    if private_key:
        pname = os.path.join(path, 'private.pem')
        with open(pname,'w') as fobj:
            fobj.write(private_key)
        os.system('chmod 0600 {0}'.format(pname))

def start_multihost(jobname, jobpath, debug=False):
    "Start the executation here."
    ansible_inventory_path = None
    config_path = jobname + '.cfg'
    print(config_path)
    vms = {} # Empty directory to store vm details
    dirs_to_delete = [] # We will delete those at the end
    config = read_multihost_config(config_path)
    ram = config.get('general').get('ram')
    vm_keys = [name for name in config.keys() if name.startswith('vm')]
    #TODO Parse the job file first
    if not os.path.exists(jobpath):
        print "Missing job file {0}".format(jobpath)
        return False

    # For extra vm(s) in the job file fail fast
    if not match_vm_numbers(vm_keys, jobpath):
        return

    # First let us create the seed image
    seed_dir = tempfile.mkdtemp()
    print('Created {0}'.format(seed_dir))
    os.system('chmod 0777 %s' % seed_dir)
    dirs_to_delete.append(seed_dir)
    meta = os.path.join(seed_dir, 'meta')
    os.makedirs(meta)
    print("Generating SSH keys")
    private_key, public_key, KEY = generate_sshkey()
    create_user_data(seed_dir, "passw0rd", atomic=False)
    create_ssh_metadata(seed_dir, public_key, private_key)
    create_seed_img(meta, seed_dir)
    seed_image = os.path.join(seed_dir, 'seed.img')

    # We will copy the seed in every vm run dir
    pkey = create_rsa_key(private_key)

    for vm_c in vm_keys:
        # Now create each vm one by one.
        # Get the current ips
        current_ips = set(scan_nmap())
        current_d = tempfile.mkdtemp()
        print('Created {0}'.format(current_d))
        os.system('chmod 0777 %s' % current_d)
        dirs_to_delete.append(current_d)
        system('cp  {0} {1}'.format(seed_image, current_d))
        # Next copy the qcow2 image
        image_path = config[vm_c].get('image')
        os.system('cp {0} {1}'.format(image_path, current_d))
        image = os.path.join(current_d, os.path.basename(image_path))

        vm = boot_qcow2(image, os.path.join(current_d, 'seed.img'), ram, vcpu='1')
        this_vm = {'process': vm}
        print("We will wait for 45 seconds for the image to boot up.")
        time.sleep(45)
        new_ips = set(scan_nmap())
        latest_ip = list(new_ips - current_ips)[0]
        this_vm['ip'] = latest_ip
        this_vm['host_string'] = latest_ip
        this_vm['user'] = config[vm_c].get('user')
        this_vm['pkey'] = pkey
        vms[vm_c] = this_vm

    # Now we are supposed to have all the vms booted.
    pprint(vms)
    inject_ip_to_vms(vms, private_key)
    ansible_flag = config.get('general').get('ansible_dir', None)
    if ansible_flag:
        dir_to_copy = ansible_flag
        if not dir_to_copy.endswith('/'):
            dir_to_copy += '/*'
        else:
            dir_to_copy += '*'
        os.system('cp -r {0} {1}'.format(dir_to_copy, seed_dir))
        ansible_inventory_path = os.path.join(seed_dir, 'tunir_ansible')
        create_ansible_inventory(vms, ansible_inventory_path)


    # This is where we test
    try:
        run_job(jobpath,job_name=jobname,vms=vms, ansible_path=seed_dir)

    finally:
        if debug:
            filename = os.path.join(seed_dir, 'destroy.sh')
            with open(filename, 'w') as fobj:
                for vm in vms.values():
                    job_pid = vm['process'].pid
                    fobj.write('kill -9 {0}\n'.format(job_pid))
                for d in dirs_to_delete:
                    fobj.write('rm -rf {0}\n'.format(d))
            print("DEBUG MODE ON. Destroy from {0}".format(filename))
            return # Do not destroy for debug case
        for vm in vms.values():
            job_pid = vm['process'].pid
            print('Killing {0}'.format(job_pid))
            os.kill(job_pid, signal.SIGKILL)
        clean_tmp_dirs(dirs_to_delete)








