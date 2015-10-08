#!/usr/bin/env python
"""Factorial project"""
from setuptools import find_packages, setup

setup(name = 'tunir',
    version = '0.9',
    description = "Simple CI system.",
    long_description = "A simple CI system which can be maintained.",
    platforms = ["Linux"],
    author="Kushal Das",
    author_email="kushaldas@gmail.com",
    url="http://tunir.rtfd.org",
    license = "GPLv2+",
    packages=find_packages(),
    data_files=[('share/tunir',
                  ['createports.py', 'default.json',
                    'default.txt', 'vgt.json', 'vgt.txt']),
        ('share/man/man8/', ['tunir.8'])],
    entry_points = {
          'console_scripts': [
              'tunir = tunirlib:startpoint'
          ]
      }
    )
