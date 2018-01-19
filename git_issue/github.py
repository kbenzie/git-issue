"""GitHub backend."""

from __future__ import print_function

from builtins import str, super

import arrow
from git_issue import GitIssueError
from git_issue.service import (Issue, IssueComment, IssueEvent, IssueNumber,
                               IssueState, Label, Milestone, Service, User,
                               get_protocol, get_repo_owner_name, get_resource,
                               get_token)
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
        protocol = get_protocol('GitHub')
        resource = get_resource('GitHub')
        self.url = '%s://%s' % (protocol, resource)
        self.api_url = '%s://api.%s' % (protocol, resource)
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
            raise GitIssueError(response)

    def issue(self, number):
        response = get('%s/issues/%s' % (self.repos_url, number),
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response)
        raise GitIssueError('could not find issue: %s' % number)

    def issues(self, state):
        states = self.states()
        if state not in [s.name for s in states]:
            raise GitIssueError('state must be one of %s' %
                                ', '.join(['"%s"' % s.name for s in states]))
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
                raise GitIssueError(response)
        return issues

    def states(self):
        return [GitHubIssueState('open'), GitHubIssueState('closed'),
                GitHubIssueState('all')]

    def user_search(self, keyword):
        response = get('%s/search/users' % self.api_url,
                       auth=self.auth,
                       headers=self.headers,
                       params={'q': keyword})
        if response.status_code == 200:
            return [GitHubUser(user) for user in response.json()['items']]
        else:
            raise GitIssueError(response)

    def labels(self):
        response = get('%s/labels' % self.repos_url,
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            labels = [GitHubLabel(label) for label in response.json()]
        else:
            raise GitIssueError(response)
        return labels

    def milestones(self):
        response = get('%s/milestones' % self.repos_url,
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            milestones = [GitHubMilestone(milestones)
                          for milestones in response.json()]
        else:
            raise GitIssueError(response)
        return milestones


class GitHubIssue(Issue):
    """GitHub Issue implementation."""

    def __init__(self, issue, auth, headers):
        super().__init__(
            GitHubIssueNumber(issue),
            issue['title'],
            issue['body'],
            GitHubIssueState(issue['state']),
            GitHubUser(issue['user']),
            issue['created_at'],
            updated=issue['updated_at'],
            assignee=GitHubUser(issue['assignee'])
            if issue['assignee'] else None,
            labels=[GitHubLabel(label) for label in issue['labels']],
            milestones=[GitHubMilestone(issue['milestone'])]
            if issue['milestone'] else [],
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
            raise GitIssueError(response)

    def comments(self):
        response = get(self.comments_url, auth=self.auth, headers=self.headers)
        if response.status_code == 200:
            return [GitHubIssueComment(comment) for comment in response.json()]
        else:
            raise GitIssueError(response)

    def events(self):
        response = get(self.events_url, auth=self.auth, headers=self.headers)
        if response.status_code == 200:
            return [GitHubIssueEvent(event) for event in response.json()]
        else:
            raise GitIssueError(response)

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
            data['milestone'] = None
            if milestone.title != 'none':
                data['milestone'] = milestone.number
        # labels (array of strings) Labels to associate with this issue.
        labels = _check_labels_(kwargs.pop('labels', []))
        if len(labels) > 0:
            data['labels'] = []
            if not any([label.name == 'none' for label in labels]):
                data['labels'] = [label.name for label in labels]
        if len(data) == 0:
            raise GitIssueError('aborted edit due to no changes')
        response = patch(
            self.issue_url, auth=self.auth, headers=self.headers, json=data)
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response)

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
            raise GitIssueError(response)

    def reopen(self):
        response = patch(
            self.issue_url,
            auth=self.auth,
            headers=self.headers,
            json={'state': 'open'})
        if response.status_code == 200:
            return GitHubIssue(response.json(), self.auth, self.headers)
        else:
            raise GitIssueError(response)

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


class GitHubIssueState(IssueState):
    """GitHub IssueState implementation."""

    def __init__(self, state):
        super().__init__(state, {'open': 'green',
                                 'closed': 'red',
                                 'all': 'reset'}[state])


class GitHubIssueEvent(IssueEvent):
    """GitHub IssueEvent implementation."""

    def __init__(self, event):
        desc = None

        # The issue was closed by the actor. When the commit_id is present, it
        # identifies the commit that closed the issue using "closes / fixes
        # #NN" syntax.
        if event['event'] == 'closed':
            desc = '%(red)sclosed%(reset)s this'
            if event['commit_id']:
                desc += ' by %s' % event['commit_id'][:8]

        # The issue was reopened by the actor.
        if event['event'] == 'reopened':
            desc = '%(green)sreopened%(reset)s this'

        # The actor subscribed to receive notifications for an issue.
        if event['event'] == 'subscribed':
            desc = 'subscribed to this'

        # The issue was merged by the actor. The `commit_id` attribute is the
        # SHA1 of the HEAD commit that was merged.
        if event['event'] == 'merged':
            desc = 'merged'
            if 'commit_id' in event:
                desc += ' by %s' % event['commit_id'][:8]

        # The issue was referenced from a commit message. The `commit_id`
        # attribute is the commit SHA1 of where that happened.
        if event['event'] == 'referenced':
            desc = 'referenced by %s' % event['commit_id'][:8]

        # The actor was @mentioned in an issue body.
        if event['event'] == 'mentioned':
            desc = 'mentioned this'

        # The issue was assigned to the actor.
        if event['event'] == 'assigned':
            if event['assigner']['id'] == event['assignee']['id']:
                desc = 'self-assigned this'
            else:
                desc = 'assigned this to %s' % GitHubUser(event['assignee'])

        # The actor was unassigned from the issue.
        if event['event'] == 'unassigned':
            desc = 'removed assignment'

        # A label was added to the issue.
        if event['event'] == 'labeled':
            desc = 'added the %s label' % GitHubLabel(event['label'])

        # A label was removed from the issue.
        if event['event'] == 'unlabeled':
            desc = 'removed the %s label' % GitHubLabel(event['label'])

        # The issue was added to a milestone.
        if event['event'] == 'milestoned':
            desc = 'added this to the %s milestone' % event['milestone'][
                'title']

        # The issue was removed from a milestone.
        if event['event'] == 'demilestoned':
            desc = 'removed from the %s milestone' % event['milestone'][
                'title']

        # The issue title was changed.
        if event['event'] == 'renamed':
            desc = 'changed the title from %(white)s{}%(reset)s'.format(event[
                'rename']['from'])
            desc += ' to %(white)s{}%(reset)s'.format(event['rename']['to'])

        # The issue was locked by the actor.
        if event['event'] == 'locked':
            desc = 'locked {}'.format('as %s ' % event['lock_reason']
                                      if 'lock_reason' in event else '')
            desc += 'and limited converstation to collaberators'

        # The issue was unlocked by the actor.
        if event['event'] == 'unlocked':
            desc = 'unlocked this converstation'

        # TODO: The pull request's branch was deleted.
        if event['event'] == 'head_ref_deleted':
            pass

        # TODO: The pull request's branch was restored.
        if event['event'] == 'head_ref_restored':
            pass

        # TODO: The actor dismissed a review from the pull request.
        if event['event'] == 'review_dismissed':
            pass

        # TODO: The actor requested review from the subject on this pull
        # request.
        if event['event'] == 'review_requested':
            pass

        # TODO: The actor removed the review request for the subject on this
        # pull request.
        if event['event'] == 'review_request_removed':
            pass

        # TODO: A user with write permissions marked an issue as a duplicate of
        # another issue or a pull request as a duplicate of another pull
        # request.
        if event['event'] == 'marked_as_duplicate':
            pass

        # TODO: An issue that a user had previously marked as a duplicate of
        # another issue is no longer considered a duplicate, or a pull request
        # that a user had previously marked as a duplicate of another pull
        # request is no longer considered a duplicate.
        if event['event'] == 'unmarked_as_duplicate':
            pass

        # The issue was added to a project board.
        if event['event'] == 'added_to_project':
            desc = 'added to project'
            if 'project' in event:
                desc += ' %s' % event['project']['name']

        # TODO: The issue was moved between columns in a project board.
        if event['event'] == 'moved_columns_in_project':
            pass

        # The issue was removed from a project board.
        if event['event'] == 'removed_from_project':
            desc = 'removed from project'
            if 'project' in event:
                desc += ' %s' % event['project']['name']

        # TODO: The issue was created by converting a note in a project board
        # to an issue.
        if event['event'] == 'converted_note_to_issue':
            pass

        if not desc:
            # TODO: Remove this once all event types are implemented
            desc = str(event['event'].replace('_', ' '))

        super().__init__(desc, GitHubUser(event['actor']), event['created_at'])


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

    def __init__(self, label=None):
        if not label:
            label = {'name': 'none', 'color': 'ffffff', 'id': 0}
        super().__init__(label['name'], label['color'])
        if 'id' in label:
            self.id = label['id']

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class GitHubMilestone(Milestone):
    """GitHub Milestone implementation."""

    def __init__(self, milestone=None):
        if not milestone:
            milestone = {
                'title': 'none',
                'description': '',
                'due_on': '%s' % arrow.utcnow(),
                'state': 'closed',
                'number': 0,
                'id': 0,
            }
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
                         comment['created_at'], comment['id'])
        self.html_url = comment['html_url']

    def url(self):
        return self.html_url
