import os
import re
import time
import shutil
import paramiko
import socket
import codecs
import logging
import subprocess
from collections import OrderedDict
from typing import List, Dict, Set, Tuple, Union, Callable, TypeVar, Any, cast
log = logging.getLogger('tunir')

T_Callable = TypeVar('T_Callable', bound=Callable[...,Any])
T_Result = TypeVar('T_Result')

STR = OrderedDict() # type: Dict[str, Dict[str, str]]

class Result(object):
    # type: (text) -> T_Result
    """
        To hold results from sshcommand executions.
    """
    def __init__(self, text):
        # type: (str) -> None
        try:
            clean_text = text.decode('utf-8')
        except AttributeError:
            clean_text = text
        self.text = clean_text # type: str
        self.return_code = None # type: int

    @property
    def stdout(self):
        # type: () -> str
        return str(self.text)

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

    def __unicode__(self):
        return unicode(self.text, encoding='utf-8', errors='replace')

def match_vm_numbers(vm_keys, jobpath):
    """Matches vm definations mentioned in config, and in the job file.

    :param vm_keys: vm(s) from the configuration
    :param jobpath: Path to the job file.
    """
    commands = [] # type: List[str]
    with open(jobpath) as fobj:
        commands = fobj.readlines()
    job_vms = {} # type: Dict[str, bool]
    for command in commands:
        if re.search('^vm[0-9] ', command):
            index = command.find(' ')
            vm_name = command[:index]
            job_vms[vm_name] = True
    job_vms_keys = job_vms.keys()
    diff = list(set(job_vms_keys) - set(vm_keys))
    if diff:
        msg = "We have extra vm(s) in job file which are not defined in configuratoin."
        log.error(msg)
        print(msg)
        print(diff)
        log.error(diff)
        return False
    return True

def create_ansible_inventory(vms, filepath):
    """Creates our inventory file for ansible

    :param vms: Dictionary containing vm details
    :param filepath: path to create the inventory file
    :return: None
    """
    text = ''
    extra = ''
    for k, v in vms.items():
        # ip hostname format for /etc/hosts
        hostname = v.get('hostname',k)
        line = "{0} ansible_ssh_host={1} ansible_ssh_user={2}\n".format(hostname,v['ip'],v['user'])
        text += line

    dirpath = os.path.dirname(filepath)
    original_inventory = os.path.join(dirpath, 'inventory')
    if os.path.exists(original_inventory):
        with open(original_inventory) as fp:
            extra = fp.read()
    with open(filepath, 'w') as fobj:
        fobj.write(text)
        if extra:
            fobj.write(extra)


def poll(config):
    "Keeps polling for a SSH connection"
    for i in range(30):
        try:
            print("Polling for SSH connection")
            result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), 'true', key_filename=config.get('key', None),
                         timeout=config.get('timeout', 60), pkey=config.get('pkey', None))
            return True
        except: # Keeping trying
            time.sleep(10)
    return False


def run(host='127.0.0.1', port=22, user='root',
                  password=None, command='/bin/true', bufsize=-1, key_filename='',
                  timeout=120, pkey=None, debug=False):
    # type(str, int, str, str, str, int, str, int, Any, bool) -> T_Result
    """
    Excecutes a command using paramiko and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param password: User password
    :param command: The command to run
    :param key_filename: SSH private key file.
    :param pkey: RSAKey if we want to login with a in-memory key
    :param debug: Boolean to print debug messages
    :return:
    """
    if debug:
        print(host, port, user)
    port = int(port)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if password:
        client.connect(hostname=host, port=port,
            username=user, password=password, banner_timeout=10)
    elif key_filename:
        client.connect(hostname=host, port=port,
            username=user, key_filename=key_filename, banner_timeout=10)
    else:
        if debug:
            print('We have a key')
        client.connect(hostname=host, port=port,
                username=user, pkey=pkey, banner_timeout=10)
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.set_combine_stderr(True)
    chan.get_pty()
    chan.exec_command(command)
    stdout = chan.makefile('r', bufsize)
    stderr = chan.makefile_stderr('r', bufsize)
    stdout_text = stdout.read()
    stderr_text = stderr.read()
    out = Result(stdout_text)
    status = int(chan.recv_exit_status())
    client.close()
    out.return_code = status
    return out

def clean_tmp_dirs(dirs):
    # type: (List[str]) -> None
    "Removes the temporary directories"
    for path in dirs:
        if os.path.exists(path) and path.startswith('/tmp'):
            shutil.rmtree(path)

def system(cmd):
    # type: (str) -> Tuple[str, str, int]
    """
    Runs a shell command, and returns the output, err, returncode

    :param cmd: The command to run.
    :return:  Tuple with (output, err, returncode).
    """
    ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, universal_newlines=True)
    out, err = ret.communicate()
    returncode = ret.returncode
    return out, err, returncode

def try_again(func):
    # type: (T_Callable) -> T_Callable
    "We will try again for ssh errors."
    def wrapper(*args, **kargs):
        try:
            result = func(*args, **kargs)
        except paramiko.ssh_exception.SSHException:
            print("Getting ssh exception, sleeping for 30 seconds and then trying again.")
            time.sleep(30)
            print("Now trying for second time.")
            result = func(*args, **kargs)
        return result
    return cast(T_Callable, wrapper)

@try_again
def execute(config, command, container=None):
    # type: (Dict[str, Any], str, bool) -> Tuple[T_Result, str]
    """
    Executes a given command based on the system.
    :param config: Configuration dictionary.
    :param command: The command to execute
    :return: (Output text, string)
    """
    result = None
    command_type = 'gating'
    command_status = {
        'gating': 'no',
        'expect_failure': 'yes',
        'non_gating': 'dontcare',
    }

    if command.startswith('@@'):
        command_type = 'expect_failure'
        command = command[3:].strip()
    elif command.startswith('##'):
        command_type = 'non_gating'
        command = command[3:].strip()

    result = run(config['host_string'], config.get('port', '22'), config['user'],
                     config.get('password', None), command, key_filename=config.get('key', None),
                     timeout=config.get('timeout', 600), pkey=config.get('pkey', None))

    negative = command_status[command_type]
    if result.return_code != 0 and command_type is 'expect_failure':  # If the command does not fail, then it is a failure.
        negative = 'yes'

    return result, negative

def update_result(result, command, negative):
    # type: (Result, str, str) -> bool
    """
    Updates the result based on input.

    :param result: Output from the command
    :param job: Job object from model.
    :param command: Text command.
    :param negative: If it is a negative command, which is supposed to fail.

    :return: Boolean, False if the job as whole is failed.
    """
    status = True
    if negative == 'yes':
        if result.return_code == 0:
            status = False
    else:
        if result.return_code != 0:
            status = False

    d = {'command': command, 'result': str(result),
         'ret': str(result.return_code), 'status': status} # type: Dict[str, Any]
    STR[command] = d


    if result.return_code != 0 and negative == 'no':
        # Save the error message and status as fail.
        return False

    return True


def run_job(jobpath, job_name='', extra_config={}, container=None,
            port=None, vms=[], ansible_path='' ):
    """
    Runs the given command using paramiko.

    :param jobpath: Path to the job file.
    :param job_name: string job name.
    :param extra_config: Configuration of the given job
    :param container: Docker object for a Docker job.
    :param port: The port number to connect in case of a vm.
    :param vms: For multihost configuration
    :param ansible_path: Path to dir with ansible details

    :return: Status of the job in boolean
    """
    if not os.path.exists(jobpath):
        print("Missing job file {0}".format(jobpath))
        return False

    # Now read the commands inside the job file
    # and execute them one by one, we need to save
    # the result too.
    commands = [] # type: List[str]
    status = True
    timeout_issue = False
    ssh_issue = False

    result_path = extra_config['result_path']
    ansible_inventory_path = None
    private_key_path = None
    private_key_path = None
    if ansible_path:
        ansible_inventory_path = os.path.join(ansible_path, 'tunir_ansible')
        if 'keypath' in vms['general']:
            private_key_path = vms['general']['keypath']
        else:
            private_key_path = os.path.join(ansible_path, 'private.pem')

    with open(jobpath) as fobj:
        commands = fobj.readlines()

    try:
        for command in commands:
            negative = ''
            result = Result('none') # type: Result
            command = command.strip(' \n')
            log.info("Next command: {0}".format(command))
            if command.startswith('SLEEP'): # We will have to sleep
                word = command.split(' ')[1]
                print("Sleeping for %s." % word)
                time.sleep(int(word))
                continue
            if command.startswith("POLL"): # We will have to POLL vm1
                #For now we will keep polling for 300 seconds.
                # TODO: fix for multivm situation
                pres = poll(vms['vm1'])
                if not pres:
                    print("Final poll failed")
                    status = False
                    break
                else:
                    continue # We don't want to execute a POLL command in the remote system
            elif command.startswith('PLAYBOOK'):
                playbook_name = command.split(' ')[1]
                playbook = os.path.join(ansible_path, playbook_name)
                cmd = "ansible-playbook {0} -i {1} --private-key={2} --ssh-extra-args='-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no'".format(playbook,\
                            ansible_inventory_path, private_key_path)
                print(cmd)
                os.system(cmd)
                continue

            print("Executing command: %s" % command)
            shell_command = command

            if re.search('^vm[0-9] ', command):
                # We have a command for multihost
                index = command.find(' ')
                vm_name = command[:index]
                shell_command = command[index+1:]
                config = vms[vm_name]
            else: #At this case, all special keywords checked, now it will run on vm1
                vm_name = 'vm1'
                shell_command = command
                config = vms[vm_name]

            try:
                result, negative = execute(config, shell_command)
                status = update_result(result, command, negative)
                if not status:
                    break
            except socket.timeout: # We have a timeout in the command
                status = False
                timeout_issue = True
                log.error("We have a socket timeout.")
                break
            except paramiko.ssh_exception.SSHException:
                status = False
                ssh_issue = True
                log.error("Getting SSHException.")
                break
            except Exception as err: #execute failed for some reason, we don't know why
                status = False
                print(err)
                log.error(err)
                break

        # If we are here, that means all commands ran successfully.

    finally:
        # Now for stateless jobs
        print("\n\nJob status: %s\n\n" % status)
        nongating = {'number':0, 'pass':0, 'fail':0}

        with codecs.open(result_path, 'w', encoding='utf-8') as fobj:
            for key, value in STR.items():
                fobj.write("command: %s\n" % value['command'])
                print("command: %s" % value['command'])
                if value['command'].startswith((' ##', '##')):
                    nongating['number'] += 1
                    if value['status'] == False:
                        nongating['fail'] += 1
                    else:
                        nongating['pass'] += 1
                fobj.write("status: %s\n" % value['status'])
                print("status: %s\n" % value['status'])
                fobj.write(value['result'])
                print(value['result'])
                fobj.write("\n")
                print("\n")

            if timeout_issue: # We have 10 minutes timeout in the last command.
                msg = "Error: We have socket timeout in the last command."
                fobj.write(msg)
                print(msg)

            if ssh_issue: # We have 10 minutes timeout in the last command.
                msg = "Error: SSH into the system failed."
                fobj.write(msg)
                print(msg)

            fobj.write("\n\n")
            print("\n\n")
            msg = """Non gating tests status:
Total:{number}
Passed:{pass}
Failed:{fail}""".format(**nongating)
            fobj.write(msg)
            print(msg)
        return status

class IPException(Exception):
    "We do not have an ip for a vm"
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)
