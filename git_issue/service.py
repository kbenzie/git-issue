"""Classes representing generic issue services."""

from abc import ABCMeta, abstractmethod
from collections import namedtuple
from os import devnull
from subprocess import CalledProcessError, check_output

import arrow
from future.utils import with_metaclass
from git_issue import GitIssueError
from giturlparse import parse
from past.builtins import basestring


def get_remote(name):
    """Get the Git remote, default to ``'origin'``.

    Arguments:
        :name: Name of the service.
    """
    with open(devnull, 'w+b') as DEVNULL:
        try:
            remote = check_output(
                ['git', 'config', '--get', 'issue.%s.remote' % name],
                stderr=DEVNULL).strip()
        except CalledProcessError:
            remote = 'origin'
        return remote


def get_resource(name):
    """Get the resource from the Git remote URL.

    Arguments:
        :name: Name of the service.

    Raises:
        :GitIssueError: If the HTTP URL could not be determined.
    """
    with open(devnull, 'w+b') as DEVNULL:
        try:
            return check_output(
                ['git', 'config', '--get'
                 'issue.%s.url' % name],
                stderr=DEVNULL).strip()
        except CalledProcessError:
            try:
                giturl = parse(
                    check_output(
                        ['git', 'config', '--get', 'remote.%s.url' %
                         get_remote(name)],
                        stderr=DEVNULL))
                return '%s' % giturl.resource
            except CalledProcessError:
                raise GitIssueError(
                    'failed to determine service HTTP URL, specify using:\n'
                    'git config issue.%s.url <url>' % name)


def get_repo_owner_name(name):
    """Get the owner/name of the remote.

    Arguments:
        :name: Name of the service.
    """
    with open(devnull, 'w+b') as DEVNULL:
        try:
            remote = parse(
                check_output(
                    ['git', 'config', '--get', 'remote.%s.url' % get_remote(
                        name)],
                    stderr=DEVNULL))
        except CalledProcessError:
            raise GitIssueError('failed to determine remote url')
        return '%s/%s' % (remote.owner, remote.name)


def get_token(name):
    """Get basic authentication header from API token.

    Arguments:
        :name: Name of the service.
    """
    try:
        token = check_output(
            ['git', 'config', '--get', 'issue.%s.token' % name]).strip()
    except CalledProcessError:
        raise GitIssueError('failed to get Gogs API token, specify using:\n'
                            'git config issue.Gogs.token <token>')
    return token


class Service(with_metaclass(ABCMeta)):
    """Abstract base class for an issue service.

    Each issue service should inherit from this class and implement each of the
    methods declared below. The command line interface will only interact with
    instances of this class to perform its actions.

    """

    def __init__(self):
        pass

    @abstractmethod
    def create(self, title, body, **data):
        """Create a new issue.

        Arguments:
            :title: Title of the issue.
            :body: Detailed description of the issue.

        Keyword Arguments:
            :assignee: ``User`` to assign the issue to.
            :labels: A list of ``Label``'s to assign to the issue.
            :milestone: A ``Milestone`` to assign to the issue.

        Returns:
            :str: URL of the created issue.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def issue(self, number):
        """Get a single issue.

        Arguments:
            :number: Number of issue to get.

        Returns:
            :Issue: The requested issue.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def issues(self, state):
        """Get a list of issues.

        Arguments:
            :state: State name for issues to get.

        Returns:
            :list: Of ``Issue`` objects.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def user_search(self, keyword):
        """Search for a user.

        Arguments:
            :keyword: Keyword of user to search for.

        Returns:
            :list: Of ``User`` objects which matched ``keyword``.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def labels(self):
        """Get a list of labels.

        Returns:
            :list: Of ``Label`` objects.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def milestones(self):
        """Get a list of milestones.

        Returns:
            :list: Of ``Milestone`` objects.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError


class Issue(with_metaclass(ABCMeta)):
    """Generic class to represent an issue.

    Arguments:
        :number: ``IssueNumber`` of this issue.
        :title: Title of the issue.
        :body: Detailed description of the issue.
        :state: Current state name for the issue.
        :author: ``User`` who created the issue.
        :created: UTC string encoded date the issue was created.

    Keyword Arguments:
        :updated: UTC string encded date the issue was updated (optional).
        :assignee: ``User`` the issue is assigned to (optional).
        :labels: ``list`` of ``Label``'s containing  (optional).
        :milestone: Name of the issue milestone (optional).
        :num_comments: Number of comments on the issue (optional).
    """

    def __init__(self, number, title, body, state, author, created, **kwargs):
        if not isinstance(number, IssueNumber):
            raise ValueError('number must be a subclass of IssueNumber')
        self.number = number
        if not isinstance(title, basestring):
            raise ValueError('title must be a string')
        self.title = title
        if not isinstance(body, basestring):
            raise ValueError('body must be a string')
        self.body = body
        if not isinstance(state,
                          basestring) or state not in ['open', 'closed']:
            raise ValueError(
                'state must be string and one of "open" or "closed"')
        self.state = state
        if not isinstance(author, User):
            raise ValueError('author must be a subclass of User')
        self.author = author
        if not isinstance(created, basestring):
            raise ValueError('created must be a string')
        self.created = arrow.get(created)
        self.updated = kwargs.pop('updated', None)
        if self.updated and not isinstance(self.updated, basestring):
            raise ValueError('updated must be a string')
        self.assignee = kwargs.pop('assignee', None)
        if self.assignee and not isinstance(self.assignee, User):
            raise ValueError('assignee must be a subclass of User')
        self.labels = kwargs.pop('labels', [])
        if isinstance(self.labels, list):
            for label in self.labels:
                if not isinstance(label, Label):
                    raise ValueError(
                        'labels must be a list of subclasses of Label')
        else:
            raise ValueError('labels must be a list of subclasses of Label')
        self.milestone = kwargs.pop('milestone', None)
        if self.milestone and not isinstance(self.milestone, Milestone):
            raise ValueError('milestone must be a subclass of Milestone')
        self.num_comments = kwargs.pop('num_comments', 0)
        if self.num_comments and not isinstance(self.num_comments, int):
            raise ValueError('comments must be an integer')

    def __lt__(self, other):
        return self.created < other.created

    @abstractmethod
    def comment(self, body):
        """Add a comment to the issue.

        Arguments:
            :body: Comment text body.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def comments(self):
        """Get list of comments.

        Returns:
            :list: Of ``IssueComment`` instances.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def events(self):
        """Get list of events.

        Returns:
            :list: Of ``IssueEvent`` instances.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def edit(self, **kwargs):
        """Edit the issue.

        Keyword Arguments:
            :title: Title of the issue.
            :body: Detailed description of the issue.
            :assignee: ``User`` to assign the issue to.
            :labels: A ``list`` of ``Label``'s to assign to the issue.
            :milestone: ``Milestone`` to assign to the issue.

        Returns:
            :str: URL of the updated issue.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self, **kwargs):
        """Close the issue.

        Keyword Arguments:
            :comment: Comment text body.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def reopen(self):
        """Reopen the issue.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError

    @abstractmethod
    def url(self):
        """Get issue HTML URL.

        Raises:
            :GitIssueError: Containing message about the error.
        """
        raise NotImplementedError


class IssueNumber(with_metaclass(ABCMeta)):
    """Generic class to represent an issue number.

    Subclasses must implement ``__str__`` to show the human facing issue number
    representation, such as ``#1``, whereas ``__repr__`` must return the value
    used when interacting with the service API, such as ``1``.
    """

    def __init__(self):
        pass

    @abstractmethod
    def __str__(self):
        raise NotImplementedError

    @abstractmethod
    def __repr__(self):
        raise NotImplementedError


class IssueComment(with_metaclass(ABCMeta)):
    """Generic class to represent an issue comment.

    Arguments:
        :body: Comment text body.
        :author: ``User`` to authored the comment.
        :created: UTC encoded date string of comment creation.
    """

    def __init__(self, body, author, created):
        self.body = body
        if not isinstance(author, User):
            raise ValueError('author must be a subclass of User')
        self.author = author
        if not created or not isinstance(created, basestring):
            raise ValueError('created must be a string')
        self.created = arrow.get(created)

    def __lt__(self, other):
        return self.created < other.created


class IssueEvent(with_metaclass(ABCMeta)):
    """Generic class to represent an issue event.

    Arguments:
        :event: String representation of the event action.
        :actor: ``User`` to action the event.
        :created: UTC encoded date string of event creation.
    """

    def __init__(self, event, actor, created):
        if event not in ['closed', 'reopened']:
            raise ValueError(
                'event must be a string of either "closed" or "reopened"')
        self.event = event
        if not isinstance(actor, User):
            raise ValueError('actor must be a subclass of User')
        self.actor = actor
        if not created or not isinstance(created, basestring):
            raise ValueError('created must be a string')
        self.created = arrow.get(created)

    def __lt__(self, other):
        return self.created < other.created


class User(with_metaclass(ABCMeta)):
    """Generic class to represent a user.

    Arguments:
        :username: Users unique API username.
        :email: Users primary email address.
        :name: Users full name.
    """

    def __init__(self, username, email, name):
        self.username = username
        self.email = email
        self.name = name

    def __str__(self):
        parts = []
        if self.name:
            parts.append(self.name)
        if self.username:
            parts.append('(%s)' % self.username)
        if self.email:
            parts.append('<%s>' % self.email)
        return ' '.join(parts)


class Label(with_metaclass(ABCMeta)):
    """Generic class to represent a label.

    Arguments:
        :name: Name of the label.
        :color: 6 character hexidecimal encoded color string.
    """

    def __init__(self, name, color):
        if not isinstance(name, basestring):
            raise ValueError('name must be a string')
        self.name = name
        if not isinstance(color, basestring) or len(color) != 6:
            raise ValueError('color must be a 6 character string')
        self.color = namedtuple('Color', 'red green blue')(int(
            color[:2], 16), int(color[2:4], 16), int(color[4:], 16))


class Milestone(with_metaclass(ABCMeta)):
    """Generic class to represent a milestone.

    Arguments:
        :title: Title of the milestone.
        :description: Description of the milestone.
        :due: UTC encoded date the milestone is due.
        :state: State of the milestone, "open" or "closed".
    """

    def __init__(self, title, description, due, state):
        if not isinstance(title, basestring):
            raise ValueError('title must be a string')
        self.title = title
        if not isinstance(description, basestring):
            raise ValueError('description must be a string')
        self.description = description
        if not isinstance(due, basestring):
            raise ValueError('due must be a UTC encoded date string')
        self.due = due
        if not isinstance(state,
                          basestring) or state not in ['open', 'closed']:
            raise ValueError(
                'state must be a string and one of "open" or "closed"')
        self.state = state
