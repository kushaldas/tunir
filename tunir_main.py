#!/usr/bin/env python

import os
import sys
import json
import time
import signal
import argparse
from pprint import pprint
from testvm import build_and_run
from fabric.api import settings, run, sudo
from fabric.network import disconnect_all
from tunirresult import download_result, text_result
from tunirdb import add_job, create_session, add_result, update_job
from tunirlib.default_config import DB_URL
from tunirdocker import Docker
from collections import OrderedDict

STR = OrderedDict()

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

def execute(system, command, container=None):
    """
    Executes a given command based on the system.
    :param system: vm, docker or bare.
    :param command: The command to execute
    :return: (Output text, boolean)
    """
    result = ''
    negative = False
    if command.startswith('@@'):
        command = command[3:].strip()
        if system == 'docker':
            result = container.execute(command)
        else:
            result = run(command)
        if result.return_code != 0:  # If the command does not fail, then it is a failure.
            negative = True
    else:
        if system == 'docker':
            result = container.execute(command)
        else:
            result = run(command)
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
            d = {'command': command, 'result': unicode(result),
                 'ret': result.return_code, 'status': True}
            STR[command] = d
        else:
            add_result(session, job.id, command, unicode(result),
                   result.return_code, status=True)
    else:
        if stateless: # For stateless
            d = {'command': command, 'result': unicode(result),
                 'ret': result.return_code, 'status': True}
            STR[command] = d
        else:
            add_result(session, job.id, command, unicode(result),
                   result.return_code)
    if result.return_code != 0 and not negative:
        # Save the error message and status as fail.
        return False

    return True


def run_job(jobpath, job_name='', config=None, container=None):
    """
    Runs the given command using fabric.

    :param jobpath: Path to the job file.
    :param job_name: string job name.
    :param config: Configuration of the given job
    :param container: Docker object for a Docker job.
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

        for command in commands:
            negative = False
            result = ''
            command = command.strip('\n')
            if command.startswith('SLEEP'): # We will have to sleep
                word = command.split(' ')[1]
                print "Sleeping for %s." % word
                time.sleep(int(word))
                continue
            if config['type'] == 'docker':
                # We want to run a container and use that.
                result, negative = execute('docker', command, container)
                status = update_result(result, session, job, command, negative, args.stateless)
                if not status:
                    break
            else:
                host_string = 'localhost:2222'
                user = 'fedora'
                password = 'passw0rd'
                if config['type'] == 'bare':
                    host_string = config['image']
                    user = config['user']
                    password = config['password']

                with settings(host_string=host_string, user=user, password=password,
                                  warn_only=True):
                    result, negative = execute(config['type'], command)
                    status = update_result(result, session, job, command, negative, args.stateless)
                    if not status:
                        break

        # If we are here, that means all commands ran successfully.
        if status:
            if not args.stateless:
                update_job(session, job)
    finally:
        disconnect_all()
        os.system('stty sane')

        # Now for stateless jobs
        if args.stateless:
            print "\n\nJob status: %s\n\n" % status

            for key, value in STR.iteritems():
                print "command: %s" % value['command']
                print "status: %s\n" % value['status']
                print value['result']
                print "\n"


def main(args):
    "Starting point of the code"
    job_name = ''
    vm = None
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
        vm = build_and_run(config['image'], config['ram'], graphics=True, vnc=False, atomic=False)
        job_pid = vm.pid # The pid to kill at the end
        # We should wait for a minute here
        time.sleep(60)
    if config['type'] == 'docker':
        container = Docker(config['image'], int(config.get('wait', 600)))
    jobpath = os.path.join(args.config_dir, job_name + '.txt')

    try:
        run_job(jobpath, job_name, config, container)
    finally:
        # Now let us kill the kvm process
        if vm:
            os.kill(job_pid, signal.SIGKILL)
        if container:
            container.rm()


if __name__ == '__main__':
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

