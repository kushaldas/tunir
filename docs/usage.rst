Usage
=====

Tunir is a continuous integration (CI) system which can run a set of commands/tests in a
new cloud VM, or bare metal, or in Docker containers based on the job configurations.
It uses fabric project to connect to the vm or bare metal tests.

The current version can be used along with cron to run at predefined times.

Enabling a queue of ports for the VMs
-------------------------------------

We maintain a queue of available ports in the local system, which will be used to create
VM(s). We maintain this queue in Redis. We have a helper script which can enable some
default ports to be used. They are defined in the *createports.py*. In case you are using
a rpm, please check */usr/share/tunir/* directory for the same.::

    $ python createports.py

.. note:: This is very important. Please have the queue with usable ports ready before any
   other step. We use ports 2222 to 2230 as the default ports available in createports.py.

Configuring a new job
----------------------

For each different job, two files are required. For example, *default* job has two files,
**default.json** and **default.txt**.

jobname.json
-------------

This file is the main configuration for the job. Below is the example of one such job.

::

    {
      "name": "jobname",
      "type": "vm",
      "image": "file:///home/vms/Fedora-Cloud-Base-20141203-21.x86_64.qcow2",
      "ram": 2048,
      "user": "fedora",
      "password": "passw0rd"
    }

The possible keys are mentioned below.

name
    The name of the job, which must match the filename.

type
    The type of system in which the tests will run. Possible values are vm, docker, bare.

image
    Path to the cloud image in case of a VM. You can provide docker image there for Docker based tests, or the ip/hostname of the bare metal box.

ram
    The amount of RAM for the VM. Optional for bare or docker types.

user
    The username to connect to.

password
    The password of the given user. Right now for cloud VM(s) it is set to *passw0rd*.

key
    The path to the ssh key, the password value should be an empty string for this.

port
    The port number as string to connect. (Required for bare type system.)

jobname.txt
------------

This text file contains the bash commands to run in the system, one command per line. In case you are
rebooting the system, you may want to use **SLEEP NUMBER_OF_SECONDS** command there.

If a command starts with @@ sign, it means the command is supposed to fail. Generally we check the return codes
of the commands to find if it failed, or not. For Docker container based systems, we track the stderr output.

Database path
-------------

We get that value from a json configuration file named *tunir.config*, either in the current directory or 
from under /etc. There is an example configuration in the source.

Create the database schema
---------------------------
::

    $ python tunirlib/createdb.py

The path of the database is configured in the tunirlib/default_config.py file. Currently it stays under /tmp.

.. note:: You do not need a database if you are only running stateless jobs.


Start a new job
---------------

::

    $ sudo ./tunir --job jobname


Find the result from a job
--------------------------

::

    $ ./tunir --result JOB_ID

The above command will create a file *result-JOB_ID.txt* in the current directory. It will overwrite any file (if exits).
In case you want to just print the result on the console use the following command.::

    $ ./tunir --result JOB_ID --text


Job configuration directory
----------------------------

You can actually provide a path to tunir so that it can pick up job configuration and commands from the given directory.::

    $ sudo ./tunir --job jobname --config-dir /etc/tunirjobs/


Stateless jobs
---------------

You can run a job as stateless, which does not require any database. This will print the result at the end of the
run.::

    $ sudo ./tunir --job jobname --stateless


Docker jobs
-------------

Docker jobs requires some work on the Docker image you want run. We will have to use a Dockerfile, and make sure
that sshd is running in that image. In case you are using a Debian based image, you will find the example in the
official `Docker documentation <https://docs.docker.com/examples/running_ssh_service/>`_.

If you want to use Fedora/CentOS images, then you can use the example `Dockerfile <https://kushal.fedorapeople.org/docker-ssh/>`_ 
I wrote.

This way in all cases (vm, bare metal, or Docker containers) tunir will work in the same way.

