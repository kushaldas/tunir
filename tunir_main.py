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

def run_command(command=''):
    """
    Runs the given command using fabric.

    :param command: string command
    :return: output of the given command
    """
    try:
        with settings(host_string="localhost:2222", user="fedora", password="passw0rd"):
            print run("free -m")
    finally:
        disconnect_all()


def main(args):
    "Starting point of the code"
    job_name = ''
    if args.job:
        job_name = args.job
    else:
        sys.exit(-2)

    # First let us read the vm configuration.
    config = read_job_configuration(job_name)
    if not config: # Bad config name
        sys.exit(-1)

    vm = build_and_run(config['image'], config['ram'], graphics=True, vnc=False, atomic=False)
    job_pid = vm.pid # The pid to kill at the end
    # We should wait for a minute here
    time.sleep(60)
    run_command()

    # Now let us kill the kvm process
    os.kill(job_pid, signal.SIGKILL)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run")
    args = parser.parse_args()
    main(args)

