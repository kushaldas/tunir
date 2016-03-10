
import os
import re
import time
import shutil
import paramiko
import socket
import codecs
import subprocess
from tunirdocker import Result
from collections import OrderedDict

STR = OrderedDict()

def run(host='127.0.0.1', port=22, user='root',
                  password=None, command='/bin/true', bufsize=-1, key_filename='',
                  timeout=120, pkey=None):
    """
    Excecutes a command using paramiko and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param password: User password
    :param command: The command to run
    :param key_filename: SSH private key file.
    :param pkey: RSAKey if we want to login with a in-memory key
    :return:
    """
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
    "Removes the temporary directories"
    for path in dirs:
        if os.path.exists(path) and path.startswith('/tmp'):
            shutil.rmtree(path)

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

def try_again(func):
    "We will try again for ssh errors."
    def wrapper(*args, **kargs):
        try:
            result = func(*args, **kargs)
        except paramiko.ssh_exception.SSHException:
            print "Getting ssh exception, sleeping for 30 seconds and then trying again."
            time.sleep(30)
            print "Now trying for second time."
            result = func(*args, **kargs)
        return result
    return wrapper

@try_again
def execute(config, command, container=None):
    """
    Executes a given command based on the system.
    :param config: Configuration dictionary.
    :param command: The command to execute
    :return: (Output text, string)
    """
    result = ''
    negative = 'no'
    if command.startswith('@@'):
        command = command[3:].strip()
        result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), command, key_filename=config.get('key', None),
                         timeout=config.get('timeout', 600), pkey=config.get('pkey', None))
        if result.return_code != 0:  # If the command does not fail, then it is a failure.
            negative = 'yes'
    elif command.startswith('##'):
        command = command[3:].strip()
        result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), command, key_filename=config.get('key', None),
                         timeout=config.get('timeout', 600), pkey=config.get('pkey', None))
        negative = 'dontcare'
    else:
        result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), command, key_filename=config.get('key', None),
                         timeout=config.get('timeout', 600), pkey=config.get('pkey', None))
    return result, negative

def update_result(result, command, negative):
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

    d = {'command': command, 'result': unicode(result, encoding='utf-8', errors='replace'),
         'ret': result.return_code, 'status': status}
    STR[command] = d


    if result.return_code != 0 and negative == 'no':
        # Save the error message and status as fail.
        return False

    return True


def run_job(jobpath, job_name='', config={}, container=None,
            port=None, vms=[] ):
    """
    Runs the given command using paramiko.

    :param jobpath: Path to the job file.
    :param job_name: string job name.
    :param config: Configuration of the given job
    :param container: Docker object for a Docker job.
    :param port: The port number to connect in case of a vm.
    :return: Status of the job in boolean
    """
    if not os.path.exists(jobpath):
        print "Missing job file {0}".format(jobpath)
        return False

    # Now read the commands inside the job file
    # and execute them one by one, we need to save
    # the result too.
    commands = []
    status = True
    timeout_issue = False
    ssh_issue = False

    result_path = config.get('result_path', '/var/run/tunir/tunir_result.txt')

    with open(jobpath) as fobj:
        commands = fobj.readlines()


    try:
        job = None
        if not vms: # Do this for anything other than multihost
            if not 'host_string' in config: # For VM based tests.
                config['host_string'] = '127.0.0.1'
            if config['type'] == 'vm':
                config['port'] = port
            elif config['type'] == 'bare':
                config['host_string'] = config['image']

        for command in commands:
            negative = False
            result = ''
            command = command.strip(' \n')
            if command.startswith('SLEEP'): # We will have to sleep
                word = command.split(' ')[1]
                print "Sleeping for %s." % word
                time.sleep(int(word))
                continue
            print "Executing command: %s" % command
            shell_command = command

            if re.search('^vm[0-9] ', command):
                # We have a command for multihost
                index = command.find(' ')
                vm_name = command[:index]
                shell_command = command[index+1:]
                config = vms[vm_name]
            try:
                result, negative = execute(config, shell_command)
                status = update_result(result, command, negative)
                if not status:
                    break
            except socket.timeout: # We have a timeout in the command
                status = False
                timeout_issue = True
                break
            except paramiko.ssh_exception.SSHException:
                status = False
                ssh_issue = True
                break
            except Exception as err: #execute failed for some reason, we don't know why
                status = False
                print err
                break

        # If we are here, that means all commands ran successfully.

    finally:
        # Now for stateless jobs
        print "\n\nJob status: %s\n\n" % status
        nongating = {'number':0, 'pass':0, 'fail':0}

        with codecs.open(result_path, 'w', encoding='utf-8') as fobj:
            for key, value in STR.iteritems():
                fobj.write("command: %s\n" % value['command'])
                print "command: %s" % value['command']
                if value['command'].startswith('##'):
                    nongating['number'] += 1
                    if value['status'] == False:
                        nongating['fail'] += 1
                    else:
                        nongating['pass'] += 1
                fobj.write("status: %s\n" % value['status'])
                print "status: %s\n" % value['status']
                fobj.write(value['result'])
                print value['result']
                fobj.write("\n")
                print "\n"
            if timeout_issue: # We have 10 minutes timeout in the last command.
                msg = "Error: We have socket timeout in the last command."
                fobj.write(msg)
                print msg
            if ssh_issue: # We have 10 minutes timeout in the last command.
                msg = "Error: SSH into the system failed."
                fobj.write(msg)
                print msg
            fobj.write("\n\n")
            print "\n\n"
            msg = """Non gating tests status:
Total:{0}
Passed:{1}
Failed:{2}""".format(nongating['number'], nongating['pass'],
                nongating['fail'])
            fobj.write(msg)
            print msg
        return status
