#!/usr/bin/env python

import os
from io import open

from setuptools import find_packages, setup


def read(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


setup(
    name="django-user-payments",
    version=__import__("user_payments").__version__,
    description="User payments and subscriptions for Django",
    long_description=read("README.rst"),
    author="Matthias Kestenholz",
    author_email="mk@feinheit.ch",
    url="https://github.com/matthiask/django-user-payments/",
    license="BSD License",
    platforms=["OS Independent"],
    packages=find_packages(exclude=["tests", "testapp"]),
    include_package_data=True,
    install_requires=["django-mooch"],
    classifiers=[
        # 'Development Status :: 5 - Production/Stable',
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    zip_safe=False,
    extras_require={"stripe": ["stripe>=2"]},
)
