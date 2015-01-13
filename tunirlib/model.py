# -*- coding: utf-8 -*-
#
# Copyright © 2015  Kushal Das <kushaldas@gmail.com>
# Copyright © 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2, or (at your option) any later
# version.  This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.  You
# should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

'''
Ukhra database model.
'''

__requires__ = ['SQLAlchemy >= 0.7', 'jinja2 >= 2.4']
import pkg_resources

import datetime
import logging
import time

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import relation
from sqlalchemy.orm import backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.collections import mapped_collection
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import and_
from sqlalchemy.sql.expression import Executable, ClauseElement

BASE = declarative_base()

ERROR_LOG = logging.getLogger('ukhra.lib.model')

# # Apparently some of our methods have too few public methods
# pylint: disable=R0903
# # Others have too many attributes
# pylint: disable=R0902
# # Others have too many arguments
# pylint: disable=R0913
# # We use id for the identifier in our db but that's too short
# pylint: disable=C0103
# # Some of the object we use here have inherited methods which apparently
# # pylint does not detect.
# pylint: disable=E1101


def create_tables(db_url, alembic_ini=None, debug=False):
    """ Create the tables in the database using the information from the
    url obtained.

    :arg db_url, URL used to connect to the database. The URL contains
        information with regards to the database engine, the host to
        connect to, the user and password and the database name.
          ie: <engine>://<user>:<password>@<host>/<dbname>
    :kwarg alembic_ini, path to the alembic ini file. This is necessary
        to be able to use alembic correctly, but not for the unit-tests.
    :kwarg debug, a boolean specifying wether we should have the verbose
        output of sqlalchemy or not.
    :return a session that can be used to query the database.

    """
    engine = create_engine(db_url, echo=debug)
    BASE.metadata.create_all(engine)
    if db_url.startswith('sqlite:'):
        # Ignore the warning about con_record
        # pylint: disable=W0613
        def _fk_pragma_on_connect(dbapi_con, con_record):
            ''' Tries to enforce referential constraints on sqlite. '''
            dbapi_con.execute('pragma foreign_keys=ON')
        sa.event.listen(engine, 'connect', _fk_pragma_on_connect)

    if alembic_ini is not None:  # pragma: no cover
        # then, load the Alembic configuration and generate the
        # version table, "stamping" it with the most recent rev:

        # Ignore the warning missing alembic
        # pylint: disable=F0401
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

    scopedsession = scoped_session(sessionmaker(bind=engine))
    return scopedsession


def drop_tables(db_url, engine):  # pragma: no cover
    """ Drops the tables in the database using the information from the
    url obtained.

    :arg db_url, URL used to connect to the database. The URL contains
    information with regards to the database engine, the host to connect
    to, the user and password and the database name.
      ie: <engine>://<user>:<password>@<host>/<dbname>
    """
    engine = create_engine(db_url)
    BASE.metadata.drop_all(engine)


class Job(BASE):
    "Each job run in the system"
    __tablename__ = 'job'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(255), nullable=False)
    image = sa.Column(sa.String(255), nullable=False)
    ram = sa.Column(sa.String(255), nullable=False)
    user = sa.Column(sa.String(255), nullable=False)
    password = sa.Column(sa.String(255), nullable=False)
    status = sa.Column(sa.Boolean, default=False)

    def __repr__(self):
        return '<Job(id=%d, name=%s, image=%s, ram=%s, user=%s, password=%s)>' % \
            (self.id, self.name, self.image, self.ram, self.user, self.password)


class Result(BASE):
    "Comments on bugs."
    __tablename__ = 'result'

    id = sa.Column(sa.Integer, primary_key=True)
    job_id = sa.Column(
        sa.Integer, sa.ForeignKey('job.id'), nullable=False)
    command = sa.Column(sa.String(255), nullable=False)
    output = sa.Column(sa.TEXT)
    return_code = sa.Column(sa.String(5), nullable=False)
    status = sa.Column(sa.Boolean)

    # Relations
    job = relation(
        'Job',
        foreign_keys=[job_id], remote_side=[Job.id],
        backref=backref('results')
    )

    def __repr__(self):
        return u'<Result(%d, %s, %s)>' % (self.id, self.command, self.status)