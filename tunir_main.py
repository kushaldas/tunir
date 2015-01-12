#!/usr/bin/env python

import os
import sys
import jsontu   tt

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


def main():
    "Starting point of the code"



if __name__ == '__main__':
    main()