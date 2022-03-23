# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='MuSiCal',
    version='0.1.0',
    description='A comprehensive toolkit for mutational signature analysis',
    long_description=readme,
    author='Hu Jin, Doga Gulhan',
    author_email='hu_jin@hms.harvard.edu, doga_gulhan@hms.harvard.edu',
    url='https://github.com/parklab/MuSiCal',
    license=license,
    packages=find_packages(exclude=('tests', 'docs', 'benchmarks',
                                    'examples', 'dev', 'images'))
)
