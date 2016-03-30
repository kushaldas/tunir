Usage
=====

Tunir is a mini continuous integration (CI) system which can run a set of commands/tests in a
new cloud VM, or bare metal, or in Vagrant boxes based on the job configurations.

The current version can be used along with cron to run at predefined times. Tunir prints
the output in the terminal, it also saves each command it ran, and the output in a text
file located at '/var/run/tunir/tunir_results.txt'.

Configuring a new job
----------------------

There are two different kinds of job configuration files, the newer one is Multi-VM config
which can take any qcow2 image and use them to boot up one or more VMs. The other option
is to use a JSON file based configuration which can be used for vm(s), vagrant images, or
bare metal remote system based testing.

For a Multi-VM configuration for a job called **default** create **default.cfg** file as
explained below. We will also require another **default.txt** file which will contain the
steps for testing.

jobname.cfg
--------------

.. versionadded:: 0.14

The following example contains a job where we are creating two VMs from the given image
files. The images can be either standard cloud image, or Atomic image. We generate ssh
keys for each run, and use that to login to the box.

::

    [general]
    cpu = 1
    ram = 1024

    [vm1]
    user = fedora
    image = /home/Fedora-Cloud-Base-20141203-21.x86_64.qcow2

    [vm2]
    user = fedora
    image = /home/Fedora-Cloud-Base-20141203-21.x86_64.qcow2

The above configuration file is self-explanatory.
Each of the vm(s) created from the above configuration will get all the other vms' IP
details in the */etc/hosts* along with vm name. Means *vm1* can ping *vm2* and vice
versa. For each run, Tunir creates a new RSA key pair and pushes the public key to each
vm, and uses the private key to do ssh based authentication.


Debugging test vm(s)
---------------------

.. versionadded:: 0.14

This can also be used a quick way to get a few vm(s) up. While using Multi-VM configuration,
one can pass **--debug** command line argument, and this will make sure that the vm(s) do not
get destroyed at the end of the tests. It will create a *destroy.sh* file, and print the path
at the end of the run. All the vm(s) will be in running condition. You can ssh into them by
using *private.key* file found in the same directory of the *destroy.sh*.

When your debugging is done, you can execute the shell script to clean up all the running instances
and any temporary file created by the previous run.

::

    # sh /tmp/tmpXYZ/destroy.sh

.. warning:: The private key remains on the disk while running Tunir in the debug mode. Please remember
   to execute the destroy.sh script to clean up afterwards.

jobname.json
-------------

This file is the main configuration for the job when we just need only one vm, or using
Vagrant, or testing on a remote vm/bare metal box. Below is the example of one such job.

::

    {
      "name": "jobname",
      "type": "vm",
      "image": "/home/vms/Fedora-Cloud-Base-20141203-21.x86_64.qcow2",
      "ram": 2048,
      "user": "fedora",
    }

The possible keys are mentioned below.

name
    The name of the job, which must match the filename.

type
    The type of system in which the tests will run. Possible values are vm, docker, bare.

image
    Path to the cloud image in case of a VM. You can provide docker image there for Docker-based tests, or the IP/hostname of the bare metal box.

ram
    The amount of RAM for the VM. Optional for bare or Docker types.

user
    The username to connect to.

password
    The password of the given user. Right now for cloud VM(s) connect using ssh key.

key
    The path to the ssh key, the password value should be an empty string for this.

port
    The port number as string to connect. (Required for bare type system.)

jobname.txt
------------

This text file contains the bash commands to run in the system, one command per line. In case you are
rebooting the system, you may want to use **SLEEP NUMBER_OF_SECONDS** command there.

If a command starts with @@ sign, it means the command is supposed to fail. Generally, we check the return codes
of the commands to find if it failed, or not. For Docker container-based systems, we track the stderr output.

We can also have non-gating tests, means these tests can pass or fail, but the whole job status will depend
on other gating tests. Any command in jobname.txt starting with ## sign will mark the test as non-gating.

Example::

    ## curl -O https://kushal.fedorapeople.org/tunirtests.tar.gz
    ls /
    ## foobar
    ## ls /root
    ##  sudo ls /root
    date
    @@ sudo reboot
    SLEEP 40
    ls /etc

For Multi-VM configurations
###########################

.. versionadded:: 0.14

In case where we are dealing with multiple VMs using .cfg file in our configuration,
we prefix each line with the vm name (like vm1, vm2, vm3). This marks which command
to run on which vm. The tool first checks the available vm names to these marks in the
*jobname.txt* file, and it will complain about any extra vm marked in there. If one
does not provide vm name, then it is assumed that the command will execute only on
vm1 (which is the available vm).

::

    vm1 sudo su -c"echo Hello > /abcd.txt"
    vm2 ls /
    vm1 ls /

In the above example the line 1, and 3 will be executed on the vm1, and line 2 will be
executed on vm2.

Using Ansible
--------------

.. versionadded:: 0.14

Along with Multi-VM configuration, we got a new feature of using
`Ansible <https://www.ansible.com/>`_ to configure the vm(s) we create. To do so,
first, create the required roles, and playbook in a given path. You can write down
the group of hosts with either naming like *vm1*, *vm2*, *vm3* or give them
proper names like *kube-master.example.com*. For the second case, we also have to
pass these hostnames in each vm definition in the configuration file. We also
provide the path to the directory containing all ansible details with *ansible_dir*
value.

Example configuration
::

    [general]
    cpu = 1
    ram = 1024
    ansible_dir = /home/user/contrib/ansible

    [vm1]
    user = fedora
    image = /home/user/Fedora-Cloud-Atomic-23-20160308.x86_64.qcow2
    hostname = kube-master.example.com

    [vm2]
    user = fedora
    image = /home/user/Fedora-Cloud-Atomic-23-20160308.x86_64.qcow2
    hostname = kube-node-01.example.com

    [vm3]
    user = fedora
    image = /home/user/Fedora-Cloud-Atomic-23-20160308.x86_64.qcow2
    hostname = kube-node-02.example.com

In the above example, we are creating 3 vm(s) with given hostnames.

.. note:: Right now all vm(s) will be using only 1 CPU. This will be changed in the future releaes.

How to execute the playbook(s)?
--------------------------------

In the *jobname.txt* you should have a **PLAYBOOK** command as given below

::

    PLAYBOOK atom.yml
    vm1 sudo atomic run projectatomic/guestbookgo-atomicapp

In this example, we are running a playbook called *atom.yml*, and then in the vm1 we
are using atomicapp to start a nulecule app :)


Execute tests on multiple pre-defined VM(s) or remote machines
---------------------------------------------------------------

::

    [general]
    cpu = 1
    ram = 1024
    ansible_dir = /home/user/contrib/ansible
    pkey = /home/user/.ssh/id_rsa

    [vm1]
    user = fedora
    ip = 192.168.122.100

    [vm2]
    user = fedora
    ip = 192.168.122.101

    [vm3]
    user = fedora
    ip = 192.168.122.102


Example of configuration file to run the tests on a remote machine
-------------------------------------------------------------------

The configuration::

    {
      "name": "remotejob",
      "type": "bare",
      "image": "192.168.1.100",
      "ram": 2048,
      "user": "fedora",
      "key": "/home/password/id_rsa"
      "port": "22"
    }




Start a new job
---------------

::

    $ sudo ./tunir --job jobname



Job configuration directory
----------------------------

You can actually provide a path to tunir so that it can pick up job configuration and commands from the given directory.::

    $ sudo ./tunir --job jobname --config-dir /etc/tunirjobs/



Timeout issue
--------------

In case if one of the commands fails to return within 10 minutes (600 seconds),
tunir will fail the job with a timeout error. It will be marked at the end of
the results. You can change the default value in the config file with a timeout
key. In the below example I am having 300 seconds as timeout for each command.::

     {
      "name": "jobname",
      "type": "vm",
      "image": "file:///home/vms/Fedora-Cloud-Base-20141203-21.x86_64.qcow2",
      "ram": 2048,
      "user": "fedora",
      "password": "passw0rd",
      "timeout": 300

    }


