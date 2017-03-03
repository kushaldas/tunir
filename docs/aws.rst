AWS support
============

.. note:: Please use the `gotun <https://gotun.readthedocs.io/en/latest/>`_ project if you want
        to spin up your instances on AWS or OpenStack.

Now we have support to use AWS for testing using Tunir. We can have both HVM,
and paravirtual types of instances to run the test. You will require `Python
libcloud <https://libcloud.apache.org/>`_ for the same.

.. note:: It boots up the instances in us-west-1 zone.

Example of HVM
---------------

The following is a JSON file containing the config of a HVM instance.
::

    {
      "name": "awsjob",
      "type": "aws",
      "image": "ami-a6fc90c6",
      "ram": 2048,
      "user": "fedora",
      "key": "PATH_TO_PEM",
      "size_id": "m3.2xlarge",
      "access_key": "YOUR_ACCESS_KEY",
      "secret_key": "YOUR_SECRET_KEY",
      "keyname": "YOUR_KEY_NAME",
      "security_group": "THE_GROUP_WITH_SSH",
      "virt_type": "hvm",
      "timeout": 30
    }

.. warning:: Remember that m3 instances are capable of running HVM.

Example of paravirtual
-----------------------

Another example with paravirtual type of instance.
::

    {
      "name": "awsjob",
      "type": "aws",
      "image": "ami-efff938f",
      "ram": 2048,
      "user": "fedora",
      "key": "PATH_TO_PEM",
      "size_id": "m1.xlarge",
      "access_key": "YOUR_ACCESS_KEY",
      "secret_key": "YOUR_SECRET_KEY",
      "keyname": "YOUR_KEY_NAME",
      "security_group": "THE_GROUP_WITH_SSH",
      "virt_type": "paravirtual",
      "aki": "aki-880531cd",
      "timeout": 30
    }
