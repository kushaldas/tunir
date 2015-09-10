import os
import sys
import json
import time
import redis
import signal
import argparse
import tempfile
import shutil
import paramiko
from pprint import pprint
from testvm import build_and_run
from tunirvagrant import vagrant_and_run
from tunirdocker import Docker, Result
from collections import OrderedDict

STR = OrderedDict()


def run(host='127.0.0.1', port=22, user='root',
                  password='passw0rd', command='/bin/true', bufsize=-1, key_filename=''):
    """
    Excecutes a command using paramiko and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param password: User password
    :param command: The command to run
    :param key_filename: SSH private key file.
    :return:
    """
    port = int(port)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if not key_filename:
        client.connect(hostname=host, port=port,
                   username=user, password=password, banner_timeout=10)
    else:
        print host, port, user, key_filename
        client.connect(hostname=host, port=port,
                   username=user, key_filename=key_filename, banner_timeout=10)
    chan = client.get_transport().open_session()
    chan.settimeout(None)
    chan.set_combine_stderr(True)
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


def read_job_configuration(jobname='', config_dir='./'):
    """
    :param jobname: Name of the job
    :param config_dir: Directory for configuration.
    :return: Configuration dict
    """
    data = None
    name = jobname + '.json'
    name = os.path.join(config_dir, name)
    if not os.path.exists(name):
        print "Job configuration is missing."
        return None
    with open(name) as fobj:
        data = json.load(fobj)
    return data

def try_again(func):
    "We will try again for ssh errors."
    def wrapper(*args, **kargs):
        try:
            result = func(*args, **kargs)
        except paramiko.ssh_exception.SSHException:
            print "Getting ssh exception, sleeping for 30 seconds and then trying again."
            time.sleep(30)
            result = func(*args, **kargs)
        return result
    return wrapper

@try_again
def execute(config, command, container=None):
    """
    Executes a given command based on the system.
    :param config: Configuration dictionary.
    :param command: The command to execute
    :return: (Output text, boolean)
    """
    result = ''
    negative = False
    if command.startswith('@@'):
        command = command[3:].strip()
        result = run(config['host_string'], config.get('port', '22'), config['user'],
                         config.get('password', None), command, key_filename=config.get('key', None))
        if result.return_code != 0:  # If the command does not fail, then it is a failure.
            negative = True
    else:
        result = run(config['host_string'], config.get('port', '22'), config['user'],
                        config.get('password', None), command, key_filename=config.get('key', None))
    return result, negative

def update_result(result, command, negative):
    """
    Updates the result based on input.

    :param result: Output from the command
    :param job: Job object from model.
    :param command: Text command.
    :param negative: If it is a negative command, which is supposed to fail.
    :param stateless: If it is a stateless job or not.

    :return: Boolean, False if the job as whole is failed.
    """
    if negative:
        status = True
        if result.return_code == 0:
            status = False
        d = {'command': command, 'result': unicode(result, encoding='utf-8', errors='replace'),
             'ret': result.return_code, 'status': status}
        STR[command] = d

    else:
        status = True
        if result.return_code != 0:
            status = False
        d = {'command': command, 'result': unicode(result, encoding='utf-8', errors='replace'),
             'ret': result.return_code, 'status': status}
        STR[command] = d

    if result.return_code != 0 and not negative:
        # Save the error message and status as fail.
        return False

    return True


def run_job(args, jobpath, job_name='', config=None, container=None, port=None):
    """
    Runs the given command using fabric.

    :param args: Command line arguments.
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

    with open(jobpath) as fobj:
        commands = fobj.readlines()


    try:
        job = None

        print "Starting a stateless job."

        if not 'host_string' in config: # For VM based tests.
            config['host_string'] = '127.0.0.1'

        if config['type'] == 'vm':
            config['port'] = port
        elif config['type'] == 'bare':
            config['host_string'] = config['image']
        elif config['type'] == 'docker':
            # Now we will convert this job as a bare metal :)
            config['type'] = 'bare'
            config['host_string'] = container.ip
            time.sleep(10)
        for command in commands:
            negative = False
            result = ''
            command = command.strip('\n')
            if command.startswith('SLEEP'): # We will have to sleep
                word = command.split(' ')[1]
                print "Sleeping for %s." % word
                time.sleep(int(word))
                continue
            print "Executing command: %s" % command

            result, negative = execute(config, command)
            status = update_result(result, command, negative)
            if not status:
                break

        # If we are here, that means all commands ran successfully.

    finally:
        # Now for stateless jobs
        print "\n\nJob status: %s\n\n" % status

        for key, value in STR.iteritems():
            print "command: %s" % value['command']
            print "status: %s\n" % value['status']
            print value['result']
            print "\n"

        return status


def get_port():
    "Gets the latest port from redis queue."
    r = redis.Redis()
    port = r.rpop('tunirports')
    print "Got port: %s" % port
    return port

def return_port(port):
    """
     Returns the port to the queue.
    :param port: The port number
    :return: None
    """
    r = redis.Redis()
    port = r.lpush('tunirports', port)
    return port

def main(args):
    "Starting point of the code"
    job_name = ''
    vm = None
    port = None
    temp_d = None
    container = None
    atomic = False
    image_dir = ''
    vagrant = None
    return_code = -100
    run_job_flag = True
    if args.atomic:
        atomic = True
    if args.job:
        job_name = args.job
    else:
        sys.exit(-2)

    # First let us read the vm configuration.
    config = read_job_configuration(job_name, args.config_dir)
    if not config: # Bad config name
        sys.exit(-1)

    if config['type'] in ['vm',]:
        # If there is an image_dir then use that, else we need to
        # create a temp directory to store the image in
        if args.image_dir:
            image_dir = args.image_dir
        else:
            temp_d = tempfile.mkdtemp()
            image_dir = temp_d
        # If the image_dir is not yet created lets create it
        if not os.path.exists(image_dir):
            os.mkdir(image_dir)
        # Create the supporting meta directory if it doesn't exist
        if not os.path.exists(os.path.join(image_dir, 'meta')):
            os.mkdir(os.path.join(image_dir, 'meta'))
        # Update perms on directory
        os.system('chmod 0777 %s' % image_dir)


    if config['type'] == 'vm':
        # First get us the free port number from redis queue.
        port = get_port()
        if not port:
            print "No port found in the redis queue."
            return
        vm = build_and_run(config['image'], config['ram'],
                           graphics=True, vnc=False, atomic=atomic,
                           port=port, image_dir=image_dir)
        job_pid = vm.pid # The pid to kill at the end
        # We should wait for a minute here
        time.sleep(60)
    if config['type'] == 'docker':
        container = Docker(config['image'])
    jobpath = os.path.join(args.config_dir, job_name + '.txt')

    if config['type'] == 'vagrant':
        vagrant, config = vagrant_and_run(config)
        if vagrant.failed:
            run_job_flag = False

    try:
        if run_job_flag:
            status = run_job(args, jobpath, job_name, config, container, port)
            if status:
                return_code = 0
    finally:
        # Now let us kill the kvm process
        if vm:
            os.kill(job_pid, signal.SIGKILL)
            if temp_d:
                shutil.rmtree(temp_d)
            return_port(port)
        if container:
            container.rm()
        if vagrant:
            print "Removing the box."
            vagrant.destroy()
        else:
            # FIXME!!!
            # Somehow the terminal is not echoing unless we do the line below.
            os.system('stty sane')
        sys.exit(return_code)


def startpoint():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run")
    parser.add_argument("--stateless", help="Do not store the result, just print it in the STDOUT.", action='store_true')
    parser.add_argument("--config-dir", help="Path to the directory where the job config and commands can be found.",
                        default='./')
    parser.add_argument("--image-dir", help="Path to the directory where vm images will be held")
    parser.add_argument("--atomic", help="We are using an Atomic image.", action='store_true')
    args = parser.parse_args()

    main(args)

if __name__ == '__main__':
    startpoint()
