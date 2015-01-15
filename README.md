## Simple CI system for specific use cases

Read the [documentation](http://tunir.rtfd.org) for more details.


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

## Rules for the commands in txt files

Write @@ at the start of the line if you know the command will fail. This will count
that command failure as a success.

## How to run the default job?

$ sudo ./tunir_main.py --job default

## How to view the result for a job_id?

% ./tunir_main.py --result job_id

