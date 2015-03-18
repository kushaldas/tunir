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
from tunirresult import download_result, text_result
from tunirdb import add_job, create_session, add_result, update_job
from default_config import DB_URL
from tunirdocker import Docker, Result
from collections import OrderedDict

STR = OrderedDict()


def run(host='127.0.0.1', port=22, user='root',
                  password='passw0rd', command='/bin/true', bufsize=-1):
    """
    Excecutes a command using paramiko and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param password: User password
    :param command: The command to run
    :return:
    """
    port = int(port)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port,
                   username=user, password=password, banner_timeout=10)
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
        result = run(config['host_string'], config['port'], config['user'],
                         config['password'], command)
        if result.return_code != 0:  # If the command does not fail, then it is a failure.
            negative = True
    else:
        result = run(config['host_string'], config['port'], config['user'],
                        config['password'], command)
    return result, negative

def update_result(result, session, job, command, negative, stateless):
    """
    Updates the result based on input.

    :param result: Output from the command
    :param session: Database session command.
    :param job: Job object from model.
    :param command: Text command.
    :param negative: If it is a negative command, which is supposed to fail.
    :param stateless: If it is a stateless job or not.

    :return: Boolean, False if the job as whole is failed.
    """
    if negative:
        if stateless: # For stateless
            status = True
            if result.return_code == 0:
                status = False
            d = {'command': command, 'result': unicode(result, encoding='utf-8', errors='replace'),
                 'ret': result.return_code, 'status': status}
            STR[command] = d
        else:
            add_result(session, job.id, command, unicode(result, encoding='utf-8', errors='replace'),
                   result.return_code, status=True)
    else:
        if stateless: # For stateless
            status = True
            if result.return_code != 0:
                status = False
            d = {'command': command, 'result': unicode(result, encoding='utf-8', errors='replace'),
                 'ret': result.return_code, 'status': status}
            STR[command] = d
        else:
            add_result(session, job.id, command, unicode(result, encoding='utf-8', errors='replace'),
                   result.return_code)
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
    :return: None
    """
    if not os.path.exists(jobpath):
        print "Missing job file."
        return

    # Now read the commands inside the job file
    # and execute them one by one, we need to save
    # the result too.
    commands = []
    status = True
    session = None
    if not args.stateless:
        session = create_session(DB_URL)

    with open(jobpath) as fobj:
        commands = fobj.readlines()


    try:
        job = None
        if not args.stateless:
            job = add_job(session, name=job_name, image=config['image'],
                          ram=config.get('ram', 0), user=config.get('user', 'root'), password=config.get('password', 'none'))
            print "Starting Job: %s" % job.id
        else:
            print "Starting a stateless job."

        config['host_string'] = '127.0.0.1'
        if config['type'] == 'vm':
            config['port'] = port
        elif config['type'] == 'bare':
            config['host_string'] = config['image']
        elif config['type'] == 'docker':
            # Now we will convert this job as a bare metal :)
            config['type'] = 'bare'
            config['port'] = int(container.port)
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
            status = update_result(result, session, job, command, negative, args.stateless)
            if not status:
                break

        # If we are here, that means all commands ran successfully.
        if status:
            if not args.stateless:
                update_job(session, job)
    finally:
        # Now for stateless jobs
        if args.stateless:
            print "\n\nJob status: %s\n\n" % status

            for key, value in STR.iteritems():
                print "command: %s" % value['command']
                print "status: %s\n" % value['status']
                print value['result']
                print "\n"


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
    if args.job:
        job_name = args.job
    else:
        sys.exit(-2)

    # First let us read the vm configuration.
    config = read_job_configuration(job_name, args.config_dir)
    if not config: # Bad config name
        sys.exit(-1)

    if config['type'] == 'vm':
        # First get us the free port number from redis queue.
        port = get_port()
        if not port:
            print "No port found in the redis queue."
            return
        # Now we need a temporary directory
        temp_d = tempfile.mkdtemp()
        os.system('chmod 0777 %s' % temp_d)
        os.mkdir(os.path.join(temp_d, 'meta'))
        vm = build_and_run(config['image'], config['ram'],
                           graphics=True, vnc=False, atomic=False,
                           port=port, temppath=temp_d)
        job_pid = vm.pid # The pid to kill at the end
        # We should wait for a minute here
        time.sleep(60)
    if config['type'] == 'docker':
        container = Docker(config['image'])
    jobpath = os.path.join(args.config_dir, job_name + '.txt')

    try:
        run_job(args, jobpath, job_name, config, container, port)
    finally:
        # Now let us kill the kvm process
        if vm:
            os.kill(job_pid, signal.SIGKILL)
            if temp_d:
                shutil.rmtree(temp_d)
            return_port(port)
        if container:
            container.rm()
        else:
            # FIXME!!!
            # Somehow the terminal is not echoing unless we do the line below.
            os.system('stty sane')


def startpoint():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run")

    parser.add_argument("--result", help="Gets the result file for the given job.")
    parser.add_argument("--text", help="Print the result.", action='store_true')
    parser.add_argument("--stateless", help="Do not store the result, just print it in the STDOUT.", action='store_true')
    parser.add_argument("--config-dir", help="Path to the directory where the job config and commands can be found.",
                        default='./')
    args = parser.parse_args()
    if args.result and args.text:
        print text_result(args.result)
        sys.exit(0)
    elif args.result:
        download_result(args.result)
        sys.exit(0)
    main(args)

if __name__ == '__main__':
    startpoint()
