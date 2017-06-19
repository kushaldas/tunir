Installation
============

Tunir is written in Python. Currently it works with Python 3.5+

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

    $ sudo dnf install libguestfs-tools python3-paramiko docker-io vagrant-libvirt ansible net-tools python3-crypto  python3-systemd python3-libcloud


.. note:: Remember to install python3-systemd package using dnf only
