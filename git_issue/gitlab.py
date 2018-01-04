"""GitLab backend."""

from __future__ import print_function

from builtins import super

from arrow import utcnow
from git_issue import GitIssueError
from git_issue.service import (Issue, IssueComment, IssueEvent, IssueNumber,
                               Label, Milestone, Service, User, get_protocol,
                               get_repo_owner_name, get_resource, get_token)
from past.builtins import basestring
from requests import get, post, put
from requests.compat import quote_plus

CACHE = {}


def _headers_():
    return {'Private-Token': get_token('GitLab')}


def _check_assignee_(assignee):
    if assignee and not isinstance(assignee, GitLabUser):
        raise GitIssueError('assignee must be an instance of GitLabUser')
    return assignee


def _check_labels_(labels):
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, GitLabLabel):
                raise ValueError(
                    'labels must be a list of GitLabLabel instances')
    else:
        raise ValueError('labels must be a list of GitLabLabel instances')
    return labels


def _check_milestone_(milestone):
    if milestone and not isinstance(milestone, GitLabMilestone):
        raise ValueError('milestone must be an instance of GitLabMilestone')
    return milestone


def _encode_state_(state):
    return {'open': 'opened', 'closed': 'closed', None: None}[state]


def _decode_state_(state):
    return {
        'opened': 'open',
        'active': 'open',
        'closed': 'closed',
        'reopened': 'open',
    }[state]


class GitLab(Service):
    """GitLab Service implementation."""

    def __init__(self):
        super().__init__()
        self.api_url = '%s://%s/api/v4' % (get_protocol('GitLab'),
                                           get_resource('GitLab'))
        self.project_url = '%s/projects/%s' % (
            self.api_url, quote_plus(get_repo_owner_name('GitLab')))
        self.issues_url = '%s/issues' % self.project_url
        self.users_url = '%s/users' % self.api_url

    def create(self, title, body, **kwargs):
        if not isinstance(title, basestring):
            raise ValueError('title must be a string')
        if not isinstance(body, basestring):
            raise ValueError('body must be a string')
        data = {'title': title, 'description': body}
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignee_ids'] = [assignee.id]
        labels = _check_labels_(kwargs.pop('labels', []))
        if labels:
            data['labels'] = [label.name for label in labels]
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone_id'] = milestone.id
        response = post(self.issues_url, headers=_headers_(), data=data)
        if response.status_code == 201:
            return GitLabIssue(response.json(), self.issues_url)
        else:
            raise GitIssueError(response)

    def issue(self, number):
        try:
            # GitLab returns a list of strings for labels, cache labels so we
            # can get their color
            CACHE['labels'] = self.labels()
        except GitIssueError:
            pass
        response = get('%s/%s' % (self.issues_url, number),
                       headers=_headers_())
        if response.status_code == 200:
            return GitLabIssue(response.json(), self.issues_url)
        else:
            raise GitIssueError(response)

    def issues(self, state):
        issues = []
        try:
            # GitLab returns a list of strings for labels, cache labels so we
            # can get their color
            CACHE['labels'] = self.labels()
        except GitIssueError:
            pass
        for state in {'open': ['open'],
                      'closed': ['closed'],
                      'all': ['open', 'closed']}[state]:
            next_url = self.issues_url
            while next_url:
                response = get(next_url,
                               headers=_headers_(),
                               params={
                                   'state': _encode_state_(state),
                                   'scope': 'all',
                                   'per_page': 100,
                               })
                if response.status_code == 200:
                    issues += [GitLabIssue(issue, self.issues_url)
                               for issue in response.json()]
                    next_url = response.links['next'][
                        'url'] if 'next' in response.links else None
                else:
                    raise GitIssueError(response)
        return reversed(sorted(issues))

    def user_search(self, keyword):
        response = get(self.users_url,
                       headers=_headers_(),
                       params={'search': keyword})
        if response.status_code == 200:
            users = [GitLabUser(user) for user in response.json()]
            if len(users) == 0:
                raise GitIssueError('unable to find user: %s' % keyword)
            return users
        else:
            raise GitIssueError(response)

    def labels(self):
        response = get('%s/labels' % self.project_url, headers=_headers_())
        if response.status_code == 200:
            return [GitLabLabel(label) for label in response.json()]
        else:
            raise GitIssueError(response)

    def milestones(self):
        response = get('%s/milestones' % self.project_url, headers=_headers_())
        if response.status_code == 200:
            return [GitLabMilestone(milestone)
                    for milestone in response.json()]
        else:
            raise GitIssueError(response)


class GitLabIssue(Issue):
    """GitLab Issue implementation."""

    def __init__(self, issue, url):
        super().__init__(
            GitLabIssueNumber(issue),
            issue['title'],
            issue['description'] if issue['description'] else '',
            _decode_state_(issue['state']),
            GitLabUser(issue['author']),
            issue['created_at'],
            updated=issue['updated_at'],
            assignee=GitLabUser(issue['assignee'])
            if issue['assignee'] else None,
            labels=[GitLabLabel(label) for label in issue['labels']],
            milestone=GitLabMilestone(issue['milestone']
                                      if issue['milestone'] else None),
            num_comments=issue['user_notes_count'])
        self.issue_url = '%s/%s' % (url, issue['iid'])
        self.notes_url = '%s/notes' % self.issue_url

    def comment(self, body):
        response = post(
            self.notes_url, headers=_headers_(), data={'body': body})
        if response.status_code == 201:
            return GitLabIssueComment(response.json())
        else:
            raise GitIssueError(response)

    def comments(self):
        comments = []
        response = get(self.notes_url, headers=_headers_())
        if response.status_code == 200:
            for note in response.json():
                if not note['system']:
                    comments.append(GitLabIssueComment(note))
        else:
            raise GitIssueError(response)
        return comments

    def events(self):
        events = []
        response = get(self.notes_url, headers=_headers_())
        if response.status_code == 200:
            for note in response.json():
                if note['system'] and note['body'] in ['closed', 'reopened']:
                    events.append(GitLabIssueEvent(note))
        else:
            raise GitIssueError(response)
        return events

    def edit(self, **kwargs):
        data = {}
        title = kwargs.pop('title', None)
        if title:
            if not isinstance(title, basestring):
                raise ValueError('title must be a string')
            data['title'] = title
        body = kwargs.pop('body', None)
        if body:
            if not isinstance(body, basestring):
                raise ValueError('body must be a string')
            data['description'] = body
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignee_ids'] = [assignee.id]
        labels = _check_labels_(kwargs.pop('labels', []))
        if labels:
            data['labels'] = ''
            if not any([label.name == 'none' for label in labels]):
                data['labels'] = [label.name for label in labels]
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone_id'] = milestone.id
        response = put(self.issue_url, headers=_headers_(), data=data)
        if len(data) == 0:
            raise GitIssueError('aborted edit due to no changes')
        if response.status_code == 200:
            return GitLabIssue(response.json(),
                               self.issue_url[:self.issue_url.rfind('/')])
        else:
            raise GitIssueError(response)

    def close(self, **kwargs):
        comment = kwargs.pop('comment', None)
        if comment:
            if not isinstance(comment, basestring):
                raise ValueError('command must be a string')
            self.comment(comment)
        response = put(self.issue_url,
                       headers=_headers_(),
                       data={'state_event': 'close'})
        if response.status_code == 200:
            return GitLabIssue(response.json(),
                               self.issue_url[:self.issue_url.rfind('/')])
        else:
            raise GitIssueError(response)

    def reopen(self):
        response = put(self.issue_url,
                       headers=_headers_(),
                       data={'state_event': 'reopen'})
        if response.status_code == 200:
            return GitLabIssue(response.json(),
                               self.issue_url[:self.issue_url.rfind('/')])
        else:
            raise GitIssueError(response)

    def url(self):
        return '%s://%s/%s/issues/%s' % (
            get_protocol('GitLab'), get_resource('GitLab'),
            get_repo_owner_name('GitLab'), self.number.iid)


class GitLabIssueNumber(IssueNumber):
    """GitLab IssueNumber implementation."""

    def __init__(self, number):
        super().__init__()
        self.id = number['id']
        self.iid = number['iid']

    def __str__(self):
        return '#%s' % self.iid

    def __repr__(self):
        return '%r' % self.iid


class GitLabIssueComment(IssueComment):
    """GitLab IssueComment implementation."""

    def __init__(self, note):
        super().__init__(note['body'], GitLabUser(note['author']),
                         note['created_at'])

    def url(self):
        # TODO: What is the URL for a comment?
        raise NotImplementedError


class GitLabIssueEvent(IssueEvent):
    """GitLab IssueEvent implementation."""

    def __init__(self, event):
        super().__init__(event['body'], GitLabUser(event['author']),
                         event['created_at'])


class GitLabUser(User):
    """GitLab User implementation."""

    def __init__(self, user):
        super().__init__(user['username'], None, user['name'])
        self.id = user['id']


class GitLabLabel(Label):
    """GitLab Label implementation."""

    def __init__(self, label=None):
        if not label:
            name = 'none'
            color = 'ffffff'
        else:
            if isinstance(label, basestring):
                # GitLab returns a list of strings for labels, cache labels so
                # we can get their color
                name = label
                if 'labels' in CACHE:
                    for l in CACHE['labels']:
                        if l.name == label:
                            color = '%x%x%x' % l.color
                else:
                    color = 'ffffff'
            else:
                name = label['name']
                color = label['color'].replace('#', '')
        super().__init__(name, color)


class GitLabMilestone(Milestone):
    """GitLab Milestone implementation."""

    def __init__(self, milestone=None):
        if not milestone:
            milestone = {'title': 'none',
                         'description': '',
                         'due_date': '%s' % utcnow(),
                         'state': 'closed',
                         'id': 0}
        super().__init__(milestone['title'], milestone['description'],
                         milestone['due_date'],
                         _decode_state_(milestone['state']))
        self.id = milestone['id']
