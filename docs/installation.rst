Installation
============

Tunir is written in Python. Currently it works with Python2.7+

Clone the repository
---------------------

::

    $ git clone https://github.com/kushaldas/tunir.git


Install the dependencies
-------------------------

We are currently depended on the following projects or libraries.

- libvirt
- libguestfs
- libguestfs-tools
- ansible
- paramiko
- vagrant-libvirt
- pycrypto
- net-tools
- typing
- python-systemd (python2-systemd package in Fedora)
- Ansible (optional)
- libcloud



You can install them in Fedora by the following command::

    $ sudo dnf install libguestfs-tools python-paramiko docker-io vagrant-libvirt ansible net-tools python-crypto python2-typing python2-systemd python-libcloud


.. note:: Remember to install python2-systemd package using dnf only
