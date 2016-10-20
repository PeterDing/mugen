
import sys


try:
    from setuptools import setup
except ImportError:
    # Use distutils.core as a fallback.
    # We won't be able to build the Wheel file on Windows.
    from distutils.core import setup

if sys.version_info < (3, 4, 0):
    raise RuntimeError("mugen requires Python 3.4.0+")

version = "0.3.0"

requires = ['httptools']

setup(
    name="mugen",
    version=version,
    author="PeterDing",
    author_email="dfhasyt@gmail.com",
    license="Apache 2.0",

    description="Mugen is library for http asynchronous requests",
    url="http://github.com/PeterDing/mugen",

    install_requires=requires,

    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],

    packages=["mugen"]
)
