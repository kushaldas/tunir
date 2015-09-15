Using Vagrant jobs
====================

`Vagrant <https://www.vagrantup.com/>`_ is a very well known system among developers for creating lightweight
development systems. Now from tunir 0.7 we can use Vagrant boxes to test. In Fedora, we can have two
different kind of vagrant provider, libvirt, and virtualbox.

.. note:: The same box can not have both libvirt and virtualbox.

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
    # dnf install VirtualBox-4.3 kernel-devel vagrant -y
    # dnf install kernel-devel -y
    # /etc/init.d/vboxdrv setup

Now try using `--provider` option with vagrant command like
::

    # vagrant up --provider virtualbox
