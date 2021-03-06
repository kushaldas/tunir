import os
import re
import sys
import time
import json
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
    def __init__(self, text) -> None:
        self.text = ""  # type: str
        if type(text) == bytes:
            self.text = text.decode('utf-8')
        else:
            self.text = text
        self.return_code = None # type: int

    @property
    def stdout(self):
        # type: () -> str
        return str(self.text)

    def __str__(self):
        return str(self.text)

    def __repr__(self):
        return self.text


class TunirConfig:
    "To hold the config and runtime vm information"
    def __init__(self) -> None:
        self.general = {}  # type: Dict[str, str]
        self.vms = {}  # type: Dict[str, Dict[str,str]]


def match_vm_numbers(vm_keys: List[str], jobpath: str) -> bool:
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
        log.error(str(diff))
        return False
    return True


def create_ansible_inventory(vms: Dict[str, Dict[str,str]], filepath: str) -> None:
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


def poll(config: Dict[str, str]) -> bool:
    "Keeps polling for a SSH connection"
    for i in range(30):
        try:
            print("Polling for SSH connection")
            result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), 'true', key_filename=config.get('key', None),
                         timeout=config.get('timeout', 60), pkey=config.get('pkey', None))
            if result.return_code == 0:
                return True
        except: # Keeping trying
            time.sleep(10)
    return False


def run(host='127.0.0.1', port='22', user='root',
                  password=None, command='/bin/true', bufsize=-1, key_filename='',
                  timeout=120, pkey=None, debug=False):
    # type(str, str, str, str, str, int, str, int, Any, bool) -> T_Result
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
        client.connect(hostname=host, port=int(port),
            username=user, password=password, banner_timeout=10)
    elif key_filename:
        client.connect(hostname=host, port=int(port),
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


def system(cmd: str) -> Tuple[str, str, int]:
    """
    Runs a shell command, and returns the output, err, returncode

    :param cmd: The command to run.
    :return:  Tuple with (output, err, returncode).
    """
    ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, universal_newlines=True)
    out, err = ret.communicate() # type: str, str
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
def execute(config: Dict[str, str], command: str, container: bool=False) -> Tuple[Result, str]:
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


def update_result(result: Result, command: str, negative: str) -> bool:
    """
    Updates the result based on input.

    :param result: Output from the command
    :param job: Job object from model.
    :param command: Text command.
    :param negative: If it is a negative command, values (yes/no).

    :return: Boolean, False if the job as whole is failed.
    """
    status = 'True'
    if negative == 'yes':
        if result.return_code == 0:
            status = ''
    else:
        if result.return_code != 0:
            status = ''

    d = {'command': command, 'result': result.text,
         'ret': str(result.return_code), 'status': status} # type: Dict[str,str]
    STR[command] = d

    if result.return_code != 0 and negative == 'no':
        # Save the error message and status as fail.
        return False

    return True

def write_ip_information(user: str, key: str, config: TunirConfig) -> None:
    """
    Writes the vm information to a JSON file
    """
    data = {"user": user, "keyfile": key}
    for key in config.vms:
        data[key] = config.vms[key]["ip"]
    with open("./current_run_info.json", "w") as fobj:
        json.dump(data, fobj)


def run_job(jobpath: str, job_name: str='', extra_config: Dict[str,str]={}, container=None,
            port: str='22', config: TunirConfig = None, ansible_path: str='' ) -> bool:
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
    status = True # type: bool
    timeout_issue = False # type: bool
    ssh_issue = False # type: bool

    result_path = extra_config['result_path']  # type: str
    ansible_inventory_path = None  # type: str
    private_key_path = None  # type: str
    if ansible_path:
        ansible_inventory_path = os.path.join(ansible_path, 'tunir_ansible')
        if 'keypath' in config.general:
            private_key_path = config.general['keypath']
        else:
            private_key_path = os.path.join(ansible_path, 'private.pem')

    write_ip_information( config.vms["vm1"]["user"], config.general["keypath"], config)
    with open(jobpath) as fobj:
        commands = fobj.readlines()

    try:
        for command in commands:
            hosttest = False
            cmd = ''
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
                #  For now we will keep polling for 300 seconds.
                #  TODO: fix for multivm situation
                pres = poll(config.vms['vm1'])
                if not pres:
                    print("Final poll failed")
                    status = False
                    break
                else:
                    continue # We don't want to execute a POLL command in the remote system
            if command.startswith("HOSTCOMMAND:"):
                cmd = command[12:].strip()
                os.system(cmd)
                continue
            elif command.startswith('HOSTTEST:'):
                cmd = command[10:].strip()
                hosttest = True


            print("Executing command: %s" % command)
            shell_command = command
            if not hosttest:
                if re.search('^vm[0-9] ', command):
                    # We have a command for multihost
                    index = command.find(' ')
                    vm_name = command[:index]
                    shell_command = command[index+1:]
                    localconfig = config.vms[vm_name]
                else: #At this case, all special keywords checked, now it will run on vm1
                    vm_name = 'vm1'
                    shell_command = command
                    localconfig = config.vms[vm_name]

            try:
                if not hosttest:
                    result, negative = execute(localconfig, shell_command)
                else: #  This is only for HOSTTEST directive
                    out, err, eid = system(cmd)
                    result = Result(out+err)
                    result.return_code = eid
                    negative = "no"
                # From here we are following the normal flow
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
                log.error(str(err))
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
                    if not value['status']:
                        nongating['fail'] += 1
                    else:
                        nongating['pass'] += 1
                fobj.write("status: %s\n" % value['status'])
                print("status: %s\n" % value['status'])
                fobj.write(str(value['result']))
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

