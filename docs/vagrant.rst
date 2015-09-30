Using Vagrant jobs
====================

`Vagrant <https://www.vagrantup.com/>`_ is a very well known system among developers for creating lightweight
development systems. Now from tunir 0.7 we can use Vagrant boxes to test. In Fedora, we can have two
different kind of vagrant provider, libvirt, and virtualbox.

.. warning:: The same host can not have both libvirt and virtualbox.

.. note:: Please create /var/run/tunir directory before running vagrant jobs.

How to install vagrant-libvirt?
--------------------------------

Just do
::

    # dnf install vagrant-libvirt

The above command will pull in all the required dependencies.

How to install Virtualbox and vagrant?
---------------------------------------

Configure required virtualbox repo
::

    # curl http://download.virtualbox.org/virtualbox/rpm/fedora/virtualbox.repo > /etc/yum.repos.d/virtualbox.repo
    # dnf install VirtualBox-4.3  vagrant -y
    # dnf install kernel-devel gcc -y
    # /etc/init.d/vboxdrv setup

Now try using `--provider` option with vagrant command like
::

    # vagrant up --provider virtualbox


Example of a libvirt based job file
------------------------------------

::

    {
      "name": "fedora",
      "type": "vagrant",
      "image": "/var/run/tunir/Fedora-Cloud-Atomic-Vagrant-22-20150521.x86_64.vagrant-libvirt.box",
      "ram": 2048,
      "user": "vagrant",
      "port": "22"
    }

Example of a Virtualbox based job file
--------------------------------------

::

    {
      "name": "fedora",
      "type": "vagrant",
      "image": "/var/run/tunir/Fedora-Cloud-Atomic-Vagrant-22-20150521.x86_64.vagrant-virtualbox.box",
      "ram": 2048,
      "user": "vagrant",
      "port": "22",
      "provider": "virtualbox"
    }

.. note:: We have a special key provider in the config for Virtualbox based jobs.
