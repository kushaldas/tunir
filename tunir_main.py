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
from tunirdb import add_job, create_session, add_result, update_job
from tunirlib.default_config import DB_URL


def read_job_configuration(jobname=''):
    """
    :param jobname: Name of the job
    :return: Configuration dict
    """
    data = None
    name = jobname + '.json'
    if not os.path.exists(name):
        print "Job configuration is missing."
        return None
    with open(name) as fobj:
        data = json.load(fobj)
    return data

def run_job(job_name='', config=None):
    """
    Runs the given command using fabric.

    :param command: string command
    :return: output of the given command
    """
    if not os.path.exists(job_name + '.txt'):
        print "Missing job file."
        return

    # Now read the commands inside the job file
    # and execute them one by one, we need to save
    # the result too.
    session = create_session(DB_URL)
    commands = []
    with open(job_name + '.txt') as fobj:
        commands = fobj.readlines()

    try:
        status = True
        job = add_job(session, name=job_name, image=config['image'],
                      ram=config['ram'], user=config['user'], password=config['password'])
        print "Starting Job: %s" % job.id
        for command in commands:
            negative = False
            command = command.strip('')
            with settings(host_string="localhost:2222", user="fedora", password="passw0rd",
                              warn_only=True):
                result = None
                if command.startswith('sudo::'): # This is a sudo command
                    result = sudo(command[6:].strip())
                elif command.startswith('@@'):
                    result = run(command[3:].strip())
                    if result.return_code != 0: # If the command does not fail, then it is a failure.
                        negative = True
                else:
                    result = run(command)
                if negative:
                    add_result(session, job.id, command, unicode(result),
                           result.return_code, status=True)
                else:
                    add_result(session, job.id, command, unicode(result),
                           result.return_code)
                if result.return_code != 0 and not negative:
                    # Save the error message and status as fail.
                    status = False
                    break
        # If we are here, that means all commands ran successfully.
        if status:
            update_job(session, job)
    finally:
        disconnect_all()


def main(args):
    "Starting point of the code"
    job_name = ''
    vm = None
    if args.job:
        job_name = args.job
    else:
        sys.exit(-2)

    # First let us read the vm configuration.
    config = read_job_configuration(job_name)
    if not config: # Bad config name
        sys.exit(-1)

    if config['type'] == 'vm':
        vm = build_and_run(config['image'], config['ram'], graphics=True, vnc=False, atomic=False)
        job_pid = vm.pid # The pid to kill at the end
        # We should wait for a minute here
        time.sleep(60)
    try:
        run_job(job_name, config)
    finally:
        # Now let us kill the kvm process
        if vm:
            os.kill(job_pid, signal.SIGKILL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run")
    args = parser.parse_args()
    main(args)

