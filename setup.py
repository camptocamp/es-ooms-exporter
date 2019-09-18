import os
from setuptools import setup, find_packages


VERSION = '1.0.0'
HERE = os.path.abspath(os.path.dirname(__file__))
INSTALL_REQUIRES = [
    pkg.split('==')[0]
    for pkg in open(os.path.join(HERE, 'requirements.txt')).read().splitlines()
]


def long_description():
    try:
        return open('README.md').read()
    except FileNotFoundError:
        return ""


setup(
    name='es-oom-exporter',
    version=VERSION,
    description="OOM prometheus exported",
    long_description=long_description(),
    long_description_content_type='text/markdown',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Plugins",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    keywords='kubernetes oom prometheus',
    author='Camptocamp',
    author_email='info@camptocamp.com',
    url='https://github.com/camptocamp/es-oom-exporter',
    license='FreeBSD',
    packages=find_packages(exclude=[]),
    include_package_data=True,
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    entry_points={
        'console_scripts': [
            'es-oom-exporter = es_oom_exporter.main:main'
        ],
    },
    scripts=[]
)
