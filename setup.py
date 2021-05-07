
from setuptools import setup

setup(
    name='sqfpack',
    description='SQF Packager',
    author='Sigmund "Sig" Klåpbakken',
    author_email='sigmundklaa@outlook.com',
    url='https://github.com/SigJig/sqfpack',
    version='0.1.0',
    install_requires=[
        'pyyaml', 'armaconfig', 'aewl'
    ],
    dependency_links=[
        'git+git://github.com/SigJig/aewl.git@main#egg=aewl',
        'git+git://github.com/SigJig/armaconfig.py.git@master#egg=armaconfig'
    ],
    packages=[
        'sqfpack'
    ]
)