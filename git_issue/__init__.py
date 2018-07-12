"""Package root for git_issue."""

from __future__ import print_function

from os import devnull
from builtins import super
from subprocess import CalledProcessError, Popen, PIPE, check_output
from requests import Response


class GitIssueError(Exception):
    """Exception class for git_issue."""

    def __init__(self, message):
        if isinstance(message, Response):
            if message.status_code == 404:
                super().__init__('issue not found')
            else:
                super().__init__('%s %s' %
                                 (message.status_code, message.reason))
        else:
            super().__init__(message)


def get_config(name):
    """Get the value of a git config option.

    Arguments:
        :name: Name of the option to get.
    """
    with open(devnull, 'w+b') as DEVNULL:
        config = check_output(
            ['git', 'config', '--get', name], stderr=DEVNULL).strip()
        if config.startswith('!'):
            process = Popen(
                config[1:], shell=True, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise GitIssueError('%s = %s\n%s' %
                                    (name, config, stderr.strip()))
            config = stdout.strip()
        return config


def get_service():
    """Get the configured service object.

    Returns:
        :Service: A subclass implementing the ``Service`` abstract base class.
    """
    try:
        name = get_config('issue.service')
        try:
            # NOTE: Import and add new services here.
            from git_issue.github import GitHub
            from git_issue.gitlab import GitLab
            from git_issue.gogs import Gogs
            return {
                'GitHub': GitHub,
                'GitLab': GitLab,
                'Gogs': Gogs,
            }[name]()
        except KeyError:
            raise GitIssueError('invalid issue service: %s' % name)
    except CalledProcessError:
        raise GitIssueError('issue service not set, specify using:\n'
                            'git config issue.service <service>')
