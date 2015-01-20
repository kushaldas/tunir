#!/usr/bin/env python
"""Factorial project"""
from setuptools import find_packages, setup

setup(name = 'tunir',
    version = '0.1',
    description = "Simple CI system.",
    long_description = "A simple CI system which can be maintained.",
    platforms = ["Linux"],
    author="Kushal Das",
    author_email="kushaldas@gmail.com",
    url="http://tunir.rtfd.org",
    license = "GPL",
    packages=find_packages(),
    data_files=[('share/tunir',
                  ['createports.py', 'default.json',
                    'default.txt', 'dockerjob.json', 'dockerjob.txt', 'tunir.config'])],
    entry_points = {
          'console_scripts': [
              'tunir = tunirlib:startpoint'
          ]
      }
    )
