#!/usr/bin/env python
"""Tunir project"""
from setuptools import find_packages, setup

setup(name = 'tunir',
    version = '0.17.3',
    description = "Simple testing system.",
    long_description = "A simple testing system which can be maintained.",
    platforms = ["Linux"],
    author="Kushal Das",
    author_email="kushaldas@gmail.com",
    url="https://tunir.readthedocs.io",
    license = "GPLv2+",
    packages=find_packages(),
    data_files=[('share/tunir',
                  ['default.json', 'multihost.txt','multihost.cfg',
                    'default.txt', 'vgt.json', 'vgt.txt']),
        ('share/man/man8/', ['tunir.8'])],
    entry_points = {
          'console_scripts': [
              'tunir = tunirlib:startpoint'
          ]
      }
    )
