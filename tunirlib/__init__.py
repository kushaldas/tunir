import os
import sys
import json
import argparse
from tunirvagrant import vagrant_and_run
from tuniraws import aws_and_run
from tunirmultihost import start_multihost
from tunirutils import run_job, Result
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

def main(args):
    "Starting point of the code"
    job_name = ''
    node = None
    debug = False
    return_code = -100
    run_job_flag = True

    if args.debug:
        debug = True
    # For multihost
    if args.multi:
        jobpath = os.path.join(args.config_dir, args.multi + '.txt')
        status = start_multihost(args.multi, jobpath, debug, config_dir=args.config_dir)
        os.system('stty sane')
        if status:
            sys.exit(0)
        else:
            sys.exit(2)
    if args.job:
        job_name = args.job
    else:
        sys.exit(-2)

    jobpath = os.path.join(args.config_dir, job_name + '.txt')


    # First let us read the vm configuration.
    config = read_job_configuration(job_name, args.config_dir)
    if not config: # Bad config name
        sys.exit(-1)

    os.system('mkdir -p /var/run/tunir')
    if config['type'] == 'vm':
        status = start_multihost(job_name, jobpath, debug, config, args.config_dir)
        if status:
            return_code = 0
        os.system('stty sane')
        sys.exit(return_code)

    if config['type'] == 'vagrant':
        node, config = vagrant_and_run(config)
        if node.failed:
            run_job_flag = False

    elif config['type'] == 'aws':
        node, config = aws_and_run(config)
        if node.failed:
            run_job_flag = False
        else:
            print "We have an instance ready in AWS.", node.node

    elif config['type'] == 'bare':
        config['host_string'] = config['image']
        config['ip'] = config['image']
        config['port'] = config.get('port', '22')
        run_job_flag = True
    try:
        if run_job_flag:
            status = start_multihost(job_name, jobpath, debug, config, args.config_dir)
            if status:
                return_code = 0
    finally:
        if config['type'] != 'bare':
            # Destroy and remove the Vagrant box or AWS instance
            node.destroy()

        sys.exit(return_code)


def startpoint():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run for JSON format file.")
    parser.add_argument("--config-dir", help="Path to the directory where the job config and commands can be found.",
                        default='./')
    parser.add_argument("--debug", help="Keep the vms running for debug in multihost mode.", action='store_true')
    parser.add_argument("--multi", help="The multivm configuration using .cfg configuration file")
    args = parser.parse_args()

    main(args)

if __name__ == '__main__':
    startpoint()
