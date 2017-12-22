"""Package root for git_issue."""

from subprocess import CalledProcessError, check_output


class GitIssueError(Exception):
    """Exception class for git_issue."""
    pass


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
            from git_issue.gogs import Gogs
            service = {
                'GitHub': GitHub(),
                'Gogs': Gogs(),
            }[name]
        except KeyError:
            raise GitIssueError('invalid issue service: %s' % name)
    except CalledProcessError:
        raise GitIssueError('issue service not set, specify using:\n'
                            'git config issue.service <service>')
    return service
