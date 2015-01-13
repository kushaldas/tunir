## Simple CI system for specific use cases

## Requirements

- libvirt
- libguestfs
- libguestfs-tools
- fabric
- sqlalchemy

To install them in Fedora use the following command.

    # dnf install libguestfs-tools fabric python-sqlalchemy

## Dev instance

First create a database using createdb.py command. You will have to
download a cloud image, which can be used to boot up the system.

For my testing I am using the Fedora 21 cloud image, I keep it
under */tmp* directory.
