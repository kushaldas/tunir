#!/usr/bin/env python
# These two lines are needed to run on EL6
__requires__ = ['SQLAlchemy >= 0.7', 'jinja2 >= 2.4']
import pkg_resources

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError


from tunirlib.default_config import DB_URL
from tunirlib import model


def create_session(db_url, debug=False, pool_recycle=3600):
    ''' Create the Session object to use to query the database.

    :arg db_url: URL used to connect to the database. The URL contains
    information with regards to the database engine, the host to connect
    to, the user and password and the database name.
      ie: <engine>://<user>:<password>@<host>/<dbname>
    :kwarg debug: a boolean specifying wether we should have the verbose
        output of sqlalchemy or not.
    :return a Session that can be used to query the database.

    '''
    engine = sqlalchemy.create_engine(
        db_url, echo=debug, pool_recycle=pool_recycle)
    scopedsession = scoped_session(sessionmaker(bind=engine))
    return scopedsession


def add_job(session, name, image, ram, user, password):
    'Adds a new job to the db.'
    job = model.Job(name=name, image=image, ram=ram, user=user, password=password)
    session.add(job)
    session.commit()
    return job

def add_result(session, job_id, command, output, return_code):
    'Adds a new result for a command'
    status = True
    if return_code != 0:
        status = False
    res = model.Result(job_id=job_id, command=command, output=output,
                       return_code=return_code, status=status )
    session.add(res)
    session.commit()

def update_job(session, job):
    job.status = True
    session.add(job)
    session.commit()


if __name__ == '__main__':
    SESSION = create_session(DB_URL)