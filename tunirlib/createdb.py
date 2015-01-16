#!/usr/bin/env python

# These two lines are needed to run on EL6
__requires__ = ['SQLAlchemy >= 0.7', 'jinja2 >= 2.4']
import pkg_resources

from tunirlib import default_config
from tunirlib import model

model.create_tables(
    default_config.DB_URL,
    None,
    debug=True)
