import os

from setuptools import find_packages, setup

VERSION = "1.0.0"
HERE = os.path.abspath(os.path.dirname(__file__))
INSTALL_REQUIRES = [
    pkg.split("==")[0] for pkg in open(os.path.join(HERE, "requirements.txt")).read().splitlines()
]


def long_description() -> str:
    try:
        return open("README.md").read()
    except FileNotFoundError:
        return ""


setup(
    name="es-oom-exporter",
    version=VERSION,
    description="OOM prometheus exported",
    long_description=long_description(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Plugins",
        "Framework :: Pyramid",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Intended Audience :: Information Technology",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Typing :: Typed",
    ],
    keywords="kubernetes oom prometheus",
    author="Camptocamp",
    author_email="info@camptocamp.com",
    url="https://github.com/camptocamp/es-oom-exporter",
    license="FreeBSD",
    packages=find_packages(exclude=[]),
    include_package_data=True,
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    entry_points={
        "console_scripts": ["es-oom-exporter = es_oom_exporter.main:main"],
    },
    package_data={"es_oom_exporter": ["py.typed"]},
)
