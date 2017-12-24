"""Setup script for git-issue."""

from platform import system

from setuptools import find_packages, setup

with open('README.rst', 'r') as readme:
    long_description = readme.read()

data_files = []
if system() != 'Windows':
    data_files += [
        ('share/man/man1', ['docs/git-issue.1']),
        ('share/zsh/site-functions', ['completion/zsh/_git-issue']),
    ]

setup(
    name='git-issue',
    version='0.2.3',
    description='Manage remote Git issue trackers',
    long_description=long_description,
    url='https://kbenzie.github.io/git-issue',
    author='Kenneth Benzie',
    autho_email='benie@infektor.net',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Bug Tracking',
        'Topic :: Software Development :: Version Control :: Git',
    ],
    keywords='command-line issue-tracker git github gogs',
    packages=find_packages(exclude=['man']),
    install_requires=[
        'arrow',
        'colorama',
        'future',
        'git-url-parse',
        'pick',
        'requests',
    ],
    entry_points={
        'console_scripts': ['git-issue=git_issue.cli:main'],
    },
    data_files=data_files)
