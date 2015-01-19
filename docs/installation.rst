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
- fabric
- sqlalchemy
- redis
- python-redis
- docker  (optional)


You can install them in Fedora by the following command::

    $ sudo dnf install libguestfs-tools fabric python-sqlalchemy docker-io python-redis redis


Start the redis server with the following command.::

    $ sudo service redis start


