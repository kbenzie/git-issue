"""Package root for git_issue."""

from __future__ import print_function

from builtins import super
from subprocess import CalledProcessError, check_output
from requests import Response


class GitIssueError(Exception):
    """Exception class for git_issue."""

    def __init__(self, message):
        if isinstance(message, Response):
            super().__init__('%s %s' % (message.status_code, message.reason))
        else:
            super().__init__(message)


def get_service():
    """Get the configured service object.

    Returns:
        :Service: A subclass implementing the ``Service`` abstract base class.
    """
    try:
        name = check_output(
            ['git', 'config', '--get', 'issue.service']).strip()
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
