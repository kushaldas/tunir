#!/usr/bin/env python

import os
import sys
import json
import argparse

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



def main(args):
    "Starting point of the code"
    job_name = ''
    if args.job:
        job_name = args.job
    else:
        sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", help="The job configuration name to run")
    args = parser.parse_args()
    main(args)
