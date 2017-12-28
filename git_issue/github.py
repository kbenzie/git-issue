"""GitHub backend."""

from __future__ import print_function

from builtins import super

from git_issue import GitIssueError
from git_issue.service import (Issue, IssueComment, IssueEvent, IssueNumber,
                               Label, Milestone, Service, User,
                               get_repo_owner_name, get_resource, get_token)
from past.builtins import basestring
from requests import get, patch, post
from requests.auth import HTTPBasicAuth

CACHE = {'users': {}}


def _check_assignee_(assignee):
    if assignee and not isinstance(assignee, GitHubUser):
        raise GitIssueError('assignee must be an instance of GitHubUser')
    return assignee


def _check_labels_(labels):
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, GitHubLabel):
                raise ValueError(
                    'labels must be a list of GitHubLabel instances')
    else:
        raise ValueError('labels must be a list of GitHubLabel instances')
    return labels


def _check_milestone_(milestone):
    if milestone and not isinstance(milestone, GitHubMilestone):
        raise ValueError('milestone must be an instance of GitHubMilestone')
    return milestone


class GitHub(Service):
    """GitHub Service implementation."""

    def __init__(self):
        super().__init__()
        resource = get_resource('GitHub')
        self.url = 'https://%s' % resource
        self.api_url = 'https://api.%s' % resource
        self.repos_url = '%s/repos/%s' % (self.api_url,
                                          get_repo_owner_name('GitHub'))
        self.issues_url = '%s/issues' % self.repos_url
        self.auth = HTTPBasicAuth(*tuple(get_token('GitHub').split(':')))
        self.headers = {'Accept': 'application/vnd.github.v3+json'}

    def create(self, title, body, **kwargs):
        # title (string) Required. The title of the issue.
        # body (string) The contents of the issue.
        if not isinstance(title, basestring):
            raise ValueError('title must be a string')
        if not isinstance(body, basestring):
            raise ValueError('body must be a string')
        data = {'title': title, 'body': body}
        # assignees (array of strings) Logins for Users to assign to this
        # issue.
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignees'] = [assignee.username]
        # milestone (integer) The number of the milestone to associate this
        # issue with.
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone'] = milestone.number
        # labels (array of strings) Labels to associate with this issue.
        labels = _check_labels_(kwargs.pop('labels', []))
        if len(labels) > 0:
            data['labels'] = [label.name for label in labels]
        response = post(
            self.issues_url, auth=self.auth, headers=self.headers, json=data)
        if response.status_code == 201:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response.reason)

    def issue(self, number):
        response = get('%s/issues/%s' % (self.repos_url, number),
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response.reason)
        raise GitIssueError('could not find issue: %s' % number)

    def issues(self, state):
        issues = []
        next_url = self.issues_url
        while next_url:
            response = get(next_url,
                           auth=self.auth,
                           headers=self.headers,
                           params={'state': state})
            if response.status_code == 200:
                issues += [GitHubIssue(issue, self.auth, self.headers)
                           for issue in response.json()]
                # If a link to the next page of issues present, use it.
                next_url = response.links['next'][
                    'url'] if 'next' in response.links else None
            else:
                raise GitIssueError(response.reason)
        return issues

    def user_search(self, keyword):
        response = get('%s/search/users' % self.api_url,
                       auth=self.auth,
                       headers=self.headers,
                       params={'q': keyword})
        if response.status_code == 200:
            return [GitHubUser(user) for user in response.json()['items']]
        else:
            raise GitIssueError(response.reason)

    def labels(self):
        response = get('%s/labels' % self.repos_url,
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return [GitHubLabel(label) for label in response.json()]
        else:
            raise GitIssueError(response.reason)

    def milestones(self):
        response = get('%s/milestones' % self.repos_url,
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return [GitHubMilestone(milestones)
                    for milestones in response.json()]
        else:
            raise GitIssueError(response.reason)


class GitHubIssue(Issue):
    """GitHub Issue implementation."""

    def __init__(self, issue, auth, headers):
        super().__init__(
            GitHubIssueNumber(issue),
            issue['title'],
            issue['body'],
            issue['state'],
            GitHubUser(issue['user']),
            issue['created_at'],
            updated=issue['updated_at'],
            assignee=GitHubUser(issue['assignee'])
            if issue['assignee'] else None,
            labels=[GitHubLabel(label) for label in issue['labels']],
            milestone=GitHubMilestone(issue['milestone'])
            if issue['milestone'] else None,
            num_comments=issue['comments'])
        self.auth = auth
        self.headers = headers
        self.issue_url = issue['url']
        self.comments_url = issue['comments_url']
        self.events_url = issue['events_url']
        self.html_url = issue['html_url']

    def comment(self, body):
        response = post(
            self.comments_url,
            auth=self.auth,
            headers=self.headers,
            json={'body': body})
        if response.status_code == 201:
            return GitHubIssueComment(response.json())
        else:
            raise GitIssueError(response.reason)

    def comments(self):
        response = get(self.comments_url, auth=self.auth, headers=self.headers)
        if response.status_code == 200:
            return [GitHubIssueComment(comment) for comment in response.json()]
        else:
            raise GitIssueError(response.reason)

    def events(self):
        response = get(self.events_url, auth=self.auth, headers=self.headers)
        if response.status_code == 200:
            events = []
            for event in response.json():
                # TODO: Currently only 'closed' and 'reopned' events are
                # supported due to limitations of other services, requires
                # changes in the comment line interface and IssueEvent. GitHub
                # has a lot of event types.
                if event['event'] in ['closed', 'reopened']:
                    events.append(GitHubIssueEvent(event))
            return events
        else:
            raise GitIssueError(response.reason)

    def edit(self, **kwargs):
        data = {}
        # title (string) Required. The title of the issue.
        title = kwargs.pop('title', None)
        if title:
            if not isinstance(title, basestring):
                raise ValueError('title must be a string')
            data['title'] = title
        body = kwargs.pop('body', None)
        if body:
            if not isinstance(body, basestring):
                raise ValueError('body must be a string')
            data['body'] = body
        # body (string) The contents of the issue.
        # assignees (array of strings) Logins for Users to assign to this
        # issue.
        assignee = _check_assignee_(kwargs.pop('assignee', None))
        if assignee:
            data['assignees'] = [assignee.username]
        # milestone (integer) The number of the milestone to associate this
        # issue with.
        milestone = _check_milestone_(kwargs.pop('milestone', None))
        if milestone:
            data['milestone'] = milestone.number
        # labels (array of strings) Labels to associate with this issue.
        labels = _check_labels_(kwargs.pop('labels', []))
        if len(labels) > 0:
            data['labels'] = [label.name for label in labels]
        if len(data) == 0:
            raise GitIssueError('aborted update due to no changes')
        response = patch(
            self.issue_url, auth=self.auth, headers=self.headers, json=data)
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response.reason)

    def close(self, **kwargs):
        comment = kwargs.pop('comment', None)
        if comment:
            if not isinstance(comment, basestring):
                raise ValueError('comment must be a string')
            self.comment(comment)
        response = patch(
            self.issue_url,
            auth=self.auth,
            headers=self.headers,
            json={'state': 'closed'})
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response.reason)

    def reopen(self):
        response = patch(
            self.issue_url,
            auth=self.auth,
            headers=self.headers,
            json={'state': 'open'})
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response.reason)

    def url(self):
        return self.html_url


class GitHubIssueNumber(IssueNumber):
    """GitHub IssueNumber implementation."""

    def __init__(self, issue):
        super().__init__()
        self.number = issue['number']
        self.id = issue['id']

    def __str__(self):
        return '#%s' % self.number

    def __repr__(self):
        return '%s' % self.number


class GitHubIssueEvent(IssueEvent):
    """GitHub IssueEvent implementation."""

    def __init__(self, event):
        super().__init__(event['event'], GitHubUser(event['actor']),
                         event['created_at'])


class GitHubUser(User):
    """GitHub User implementation."""

    def __init__(self, user):
        # To avoid fetching the additional user (name, email) multiple times
        # the results are cached.
        self.id = user['id']
        if self.id not in CACHE['users']:
            response = get(user['url'])
            if response.status_code == 200:
                CACHE['users'][self.id] = response.json()
        more = CACHE['users'][self.id] if self.id in CACHE['users'] else None
        super().__init__(user['login'], more['email']
                         if more else None, more['name'] if more else None)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GitHubLabel(Label):
    """GitHub Label implementation."""

    def __init__(self, label):
        super().__init__(label['name'], label['color'])
        self.id = label['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GitHubMilestone(Milestone):
    """GitHub Milestone implementation."""

    def __init__(self, milestone):
        super().__init__(milestone['title'], milestone['description'],
                         milestone['due_on'], milestone['state'])
        self.number = milestone['number']
        self.id = milestone['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GitHubIssueComment(IssueComment):
    """GitHub IssueComment implementation."""

    def __init__(self, comment):
        super().__init__(comment['body'], GitHubUser(comment['user']),
                         comment['created_at'])
        self.html_url = comment['html_url']

    def url(self):
        return self.html_url
