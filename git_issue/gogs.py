"""Gogs backend."""

from __future__ import print_function

from builtins import super
from warnings import warn

from git_issue import GitIssueError
from git_issue.service import (Issue, IssueComment, IssueEvent, IssueNumber,
                               Label, Milestone, Service, User,
                               get_repo_owner_name, get_resource, get_token)
from past.builtins import basestring
from requests import get, patch, post


def _check_assignee_(assignee):
    if assignee:
        if not isinstance(assignee, GogsUser):
            raise ValueError('assignee must be an instance of GogsUser')
    return assignee


def _check_labels_(labels):
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, GogsLabel):
                raise ValueError(
                    'labels must be a list of GogsLabel instances')
    else:
        raise ValueError('labels must be a list of GogsLabel instances')
    return labels


def _check_milestone_(milestone):
    if milestone:
        if not isinstance(milestone, GogsMilestone):
            raise ValueError('milestone must be an instance of GogsMilestone')
    return milestone


class Gogs(Service):
    """Gogs Service implementation."""

    def __init__(self):
        super().__init__()
        self.url = 'https://%s' % get_resource('Gogs')
        self.api_url = '%s/api/v1' % self.url
        self.repos_url = '%s/repos/%s' % (self.api_url,
                                          get_repo_owner_name('Gogs'))
        self.header = {'Authorization': 'token %s' % get_token('Gogs')}

    def create(self, title, body, **kwargs):
        # title (string) The title of the issue
        # body (string) The contents of the issue
        if not isinstance(title, basestring):
            raise ValueError('title must be a string')
        if not isinstance(body, basestring):
            raise ValueError('body must be a string')
        data = {'title': title, 'body': body}
        # assignee (string) Username for the user that this issue should be
        # assigned to.
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignee'] = assignee.username
        # labels (array of int) Labels ID to associate with this issue.
        labels = _check_labels_(kwargs.pop('labels', []))
        if len(labels) > 0:
            data['labels'] = [label.id for label in labels]
        # milestone (int) The ID of the milestone to associate this issue with.
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone'] = milestone.id
        response = post(
            '%s/issues' % self.repos_url, json=data, headers=self.header)
        if response.status_code == 201:
            return response.json()
        else:
            raise GitIssueError(response.reason)

    def issue(self, number):
        response = get('%s/issues/%s' % (self.repos_url, number),
                       headers=self.header)
        if response.status_code == 200:
            return GogsIssue(response.json(), self.repos_url, self.header)
        else:
            raise GitIssueError(response.reason)

    def issues(self, state):
        # Parameters are not documented, this is from the Gogs issue page URL.
        #   ?type=all&sort=&state=closed&labels=0&milestone=0&assignee=0
        # state seems to be the only one which works for api/v1.
        if state not in ['open', 'closed', 'all']:
            raise ValueError(
                'state must be a string and one of "open", "closed", or "all"')
        issues = []
        # Gogs does't not support 'all' so we must iterate over 'open' and
        # 'closed' states to get all issues.
        for state in {'open': ['open'],
                      'closed': ['closed'],
                      'all': ['open', 'closed']}[state]:
            next_url = '%s/issues' % self.repos_url
            while next_url:
                response = get(next_url,
                               headers=self.header,
                               params={'state': state})
                if response.status_code == 200:
                    issues += [GogsIssue(issue, self.repos_url, self.header)
                               for issue in response.json()]
                    # If a link to the next page of issues present, use it.
                    next_url = response.links['next'][
                        'url'] if 'next' in response.links else None
                else:
                    raise GitIssueError(response.reason)
        return reversed(sorted(issues))

    def labels(self):
        response = get('%s/labels' % self.repos_url, headers=self.header)
        if response.status_code == 200:
            labels = [GogsLabel(label) for label in response.json()]
        else:
            raise GitIssueError(response.reason)
        return labels

    def milestones(self):
        response = get('%s/milestones' % self.repos_url, headers=self.header)
        if response.status_code == 200:
            milestones = [GogsMilestone(milestone)
                          for milestone in response.json()]
        else:
            raise GitIssueError(response.reason)
        return milestones

    def user_search(self, keyword):
        response = get('%s/users/search' % self.api_url,
                       headers=self.header,
                       params={'q': keyword})
        if response.status_code == 200:
            users = response.json()['data']
        else:
            raise GitIssueError(response.reason)
        if len(users) == 0:
            raise GitIssueError('unable to find user: %s' % keyword)
        return [GogsUser(user) for user in users]


class GogsIssue(Issue):
    """Gogs Issue implementation."""

    def __init__(self, issue, repos_url, header):
        super().__init__(
            GogsIssueNumber(issue),
            issue['title'],
            issue['body'],
            issue['state'],
            GogsUser(issue['user']),
            issue['created_at'],
            updated=issue['updated_at'],
            assignee=GogsUser(issue['assignee'])
            if issue['assignee'] else None,
            labels=[GogsLabel(label) for label in issue['labels']],
            milestone=GogsMilestone(issue['milestone'])
            if issue['milestone'] else None,
            num_comments=issue['comments'])
        self.issues_url = '%s/issues' % repos_url
        self.header = header
        self.cache = {}

    def comment(self, body):
        response = post(
            '%s/%r/comments' % (self.issues_url, self.number),
            headers=self.header,
            json={'body': body})
        if response.status_code == 201:
            return response.json()
        else:
            raise GitIssueError(response.reason)

    def _comments_(self):
        response = get('%s/%r/comments' % (self.issues_url, self.number),
                       headers=self.header)
        if response.status_code == 200:
            self.cache['comments'] = response.json()
        else:
            raise GitIssueError(response.reason)

    def comments(self):
        # NOTE: Gogs reports events as comments with an empty body, so we cache
        # the data instead of getting it twice.
        if 'comments' not in self.cache:
            self._comments_()
        comments = []
        for comment in self.cache['comments']:
            if len(comment['body']) > 0:
                comments.append(GogsIssueComment(comment))
        return comments

    def events(self):
        # NOTE: Gogs reports events as comments with an empty body, so we cache
        # the data instead of getting it twice.
        if 'comments' not in self.cache:
            self._comments_()
        # NOTE: Gogs issues can begin in a closed state so to correctly
        # determine the state change for each action we must work from issues
        # current state and rely on the reverse order of the served comments.
        state = self.state
        events = []
        for event in self.cache['comments']:
            if len(event['body']) == 0:
                events.append(
                    GogsIssueEvent({'open': 'reopened',
                                    'closed': 'closed'}[state], event))
                state = {'open': 'closed', 'closed': 'open'}[state]
        return events

    def edit(self, **kwargs):
        data = {}
        # title (string) The title of the issue
        title = kwargs.pop('title', None)
        if title:
            if not isinstance(title, basestring):
                raise ValueError('title must be a string')
            data['title'] = title
        # body (string) The contents of the issue
        body = kwargs.pop('body', None)
        if body:
            if not isinstance(body, basestring):
                raise ValueError('body must be a string')
            data['body'] = body
        # assignee (string) Username for the user that this issue should be
        # assigned to.
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignee'] = assignee.username
        # labels (array of int) Labels ID to associate with this issue.
        labels = _check_labels_(kwargs.pop('labels', []))
        if len(labels) > 0:
            # TODO: Update this if/when Gogs adds support for editing labels.
            warn('Gogs does not support editing labels, attepmting anyway')
            data['labels'] = [label.id for label in labels]
        # milestone (int) The ID of the milestone to associate this issue with.
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone'] = milestone.id
        if len(data) == 0:
            raise GitIssueError('aborted update due to no changes')
        response = patch(
            '%s/%r' % (self.issues_url, self.number),
            headers=self.header,
            json=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise GitIssueError(response.reason)

    def close(self, **kwargs):
        comment = kwargs.pop('comment', None)
        if comment:
            if not isinstance(comment, basestring):
                raise ValueError('comment must be a string')
            self.comment(comment)
        response = patch(
            '%s/%r' % (self.issues_url, self.number),
            headers=self.header,
            json={'state': 'closed'})
        if response.status_code == 201:
            return response.json()
        else:
            raise GitIssueError(response.reason)

    def reopen(self):
        response = patch(
            '%s/%r' % (self.issues_url, self.number),
            headers=self.header,
            json={'state': 'open'})
        if response.status_code == 201:
            return response.json()
        else:
            raise GitIssueError(response.reason)

    def url(self):
        return '%s/%s/issues/%r' % (self.url, get_repo_owner_name('Gogs'),
                                    self.number)


class GogsIssueNumber(IssueNumber):
    """Gogs IssueNumber implementation."""

    def __init__(self, issue):
        super().__init__()
        self.number = issue['number']
        self.id = issue['id']

    def __str__(self):
        return '#%s' % self.number

    def __repr__(self):
        return '%s' % self.number


class GogsIssueComment(IssueComment):
    """Gogs IssueComment implementation."""

    def __init__(self, comment):
        super().__init__(comment['body'], GogsUser(comment['user']),
                         comment['created_at'])


class GogsIssueEvent(IssueEvent):
    """Gogs IssueEvent implementation."""

    def __init__(self, action, event):
        super().__init__(action, GogsUser(event['user']), event['created_at'])


class GogsUser(User):
    """Gogs User implementation."""

    def __init__(self, user):
        super().__init__(user['username'], user['email'], user['full_name'])
        self.id = user['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GogsLabel(Label):
    """Gogs Label implementation."""

    def __init__(self, label):
        super().__init__(label['name'], label['color'])
        self.id = label['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GogsMilestone(Milestone):
    """Gogs Milestone implementation."""

    def __init__(self, milestone):
        super().__init__(milestone['title'], milestone['description'],
                         milestone['due_on'], milestone['state'])
        self.id = milestone['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id
