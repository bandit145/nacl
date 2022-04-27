#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("requirements.txt", "r") as reqs:
    requirements = reqs.readlines()

setup(
    name="nacl",
    version="0.1.0",
    description="Easily dev and test Salt Stack formulas locally",
    author="Philip Bove",
    install_requires=requirements,
    author_email="phil@bove.online",
    packages=find_packages(),
    scripts=["bin/nacl"],
)
