"""Setup script for git-issue."""

from platform import system

from setuptools import find_packages, setup

data_files = []
if system() != 'Windows':
    data_files += [
        ('share/man/man1', ['docs/git-issue.1']),
        ('share/zsh/site-functions', ['completion/zsh/_git-issue']),
    ]

setup(
    name='git_issue',
    version='0.2.5',
    description='Manage remote Git issue trackers',
    url='https://code.infektor.net/benie/git-issue',
    author='Kenneth Benzie',
    autho_email='benie@infektor.net',
    license='MIT',
    classifiers=[
        'Development Status :: 1 - Planning',
    ],
    keywords='git issue track gogs',
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
