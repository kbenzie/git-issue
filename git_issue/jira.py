"""JIRA backend."""

from __future__ import print_function

from builtins import str, super
from subprocess import CalledProcessError

from git_issue import GitIssueError, get_config
from git_issue.service import (Issue, IssueComment, IssueEvent, IssueNumber,
                               IssueState, Label, Milestone, Service, User,
                               get_token, get_url)
from past.builtins import basestring
from requests import get, post
from requests.auth import HTTPBasicAuth

CACHE = {}

COLORS = {
    'blue-gray': 'blue',
    'yellow': 'lightyellow',
    'green': 'green',
}

ISSUE_FIELDS = [
    'assignee',
    'comment',
    'created',
    'description',
    'components',
    'reporter',
    'status',
    'summary',
    'updated',
    'fixVersions',
]


def _get_key_():
    if 'api_key' not in CACHE:
        try:
            CACHE['api_key'] = get_config('issue.JIRA.key')
        except CalledProcessError:
            raise GitIssueError('JIRA project key not set, specify using:\n'
                                'git config issue.JIRA.key <key>')
    return CACHE['api_key']


def _get_auth_():
    if 'api_auth' not in CACHE:
        CACHE['api_auth'] = HTTPBasicAuth(*tuple(get_token('JIRA').split(':')))
    return CACHE['api_auth']


def _get_headers_():
    if 'api_headers' not in CACHE:
        CACHE['api_headers'] = {'Accept': 'application/json',
                                'Content-Type': 'application/json'}
    return CACHE['api_headers']


class JIRA(Service):
    """JIRA Service implementation."""

    def __init__(self):
        super().__init__()
        self.url = get_url('JIRA')
        self.key = _get_key_()
        self.auth = _get_auth_()
        self.headers = _get_headers_()
        self.api_url = '%s/rest/api/2' % self.url
        self.project_url = '%s/project/%s' % (self.api_url, self.key)
        self.search_url = '%s/search' % self.api_url
        self.issue_url = '%s/issue' % self.api_url

    def create(self, title, body, **kwargs):
        raise NotImplementedError

    def issue(self, number):
        if 'states' not in CACHE:
            response = get('%s/status' % self.api_url,
                           auth=self.auth,
                           headers=self.headers)
            if response.status_code == 200:
                CACHE['states'] = {state.name: state
                                   for state in self.states()}
        response = get('%s/%s' % (self.issue_url, number),
                       auth=self.auth,
                       headers=self.headers,
                       params={
                           'fields': ISSUE_FIELDS,
                           'expand': 'changelog'
                       })
        if response.status_code == 200:
            return JIRAIssue(response.json())
        else:
            raise GitIssueError(response)

    def issues(self, state):
        # TODO: Support minimal fetch for speedy completion of issues
        states = ['open', 'closed', 'all'] + [s.name for s in self.states()]
        if state not in states:
            raise GitIssueError('state must be one of %s' % ', '.join(
                ['"%s"' % s for s in states]))
        start_at = 0
        issues = []
        while True:
            jql = 'project="%s"' % self.key
            try:
                # Support "open", "closed", and "all" to maintain a familiar
                # interface for all services and support issue completions
                # without two requests. Implemented in terms of statusCategory
                # which each status is a member of.
                jql += '&' + {
                    'open': 'statusCategory!="Done"',
                    'closed': 'statusCategory="Done"',
                    'all': '',
                }[state]
            except KeyError:
                # Support available status values queried from JIRA for
                # explicit control over return issues.
                jql += '&status="%s"' % state
            response = get(self.search_url,
                           auth=self.auth,
                           headers=self.headers,
                           params={
                               'jql': jql,
                               'startAt': start_at,
                               'fields': ISSUE_FIELDS
                           })
            if response.status_code == 200:
                result = response.json()
                issues += result['issues']
                start_at += result['maxResults']
                if start_at > result['total']:
                    break
            else:
                raise GitIssueError(response)
        return [JIRAIssue(issue) for issue in issues]

    def states(self):
        response = get('%s/status' % self.api_url,
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return [JIRAIssueState(state) for state in response.json()]
        else:
            raise GitIssueError(response)

    def user_search(self, keyword):
        response = get('%s/user/search' % self.api_url,
                       auth=self.auth,
                       headers=self.headers,
                       params={'username': keyword})
        if response.status_code == 200:
            return JIRAUser(response.json())
        else:
            raise GitIssueError(response)

    def labels(self):
        response = get(self.project_url, auth=self.auth, headers=self.headers)
        if response.status_code == 200:
            return [JIRALabel(label)
                    for label in response.json()['components']]
        else:
            raise GitIssueError(response)

    def milestones(self):
        response = get('%s/project/%s/versions' % (self.api_url, self.key),
                       auth=self.auth,
                       headers=self.headers)
        if response.status_code == 200:
            return [JIRAMilestone(milestone) for milestone in response.json()]
        else:
            raise GitIssueError(response)


class JIRAIssue(Issue):
    """JIRA Issue implementation."""

    def __init__(self, issue):
        self.auth = _get_auth_()
        self.headers = _get_headers_()
        self.key = issue['key']
        self.issue_url = issue['self']
        self.fields = issue['fields']
        super().__init__(
            JIRAIssueNumber(issue),
            self.fields['summary'],
            self.fields['description'] if self.fields['description'] else '',
            JIRAIssueState(self.fields['status']),
            JIRAUser(self.fields['reporter']),
            self.fields['created'],
            updated=self.fields['updated'],
            assignee=JIRAUser(self.fields['assignee'])
            if self.fields['assignee'] else None,
            labels=[JIRALabel(label) for label in self.fields['components']],
            milestones=[JIRAMilestone(milestone)
                        for milestone in self.fields['fixVersions']],
            num_comments=self.fields['comment']['total'])
        self.issue_url = issue['self']
        self.changelog = None
        if 'changelog' in issue:
            self.changelog = issue['changelog']

    def comment(self, body):
        response = post(
            '%s/comment' % self.issue_url,
            auth=self.auth,
            headers=self.headers,
            data={'body': body})
        if response.status_code == 201:
            return JIRAIssueComment(response.json(), self.issue_url)
        else:
            raise GitIssueError(response)

    def comments(self):
        return [JIRAIssueComment(comment, self.url())
                for comment in self.fields['comment']['comments']]

    def events(self):
        events = []
        if self.changelog:
            events = [JIRAIssueEvent(event)
                      for event in self.changelog['histories']]
        return events

    def edit(self, **kwargs):
        raise NotImplementedError

    def move(self, **kwargs):
        raise NotImplementedError

    def close(self, **kwargs):
        raise NotImplementedError

    def reopen(self):
        raise NotImplementedError

    def url(self):
        return '%s/browse/%s' % (get_url('JIRA'), self.key)


class JIRAIssueNumber(IssueNumber):
    """JIRA IssueNumber implementation."""

    def __init__(self, issue):
        super().__init__()
        self.key = issue['key']

    def __str__(self):
        return self.key

    def __repr__(self):
        return self.key


class JIRAIssueState(IssueState):
    """JIRA IssueState implementation."""

    def __init__(self, state):
        if isinstance(state, basestring):
            if 'states' in CACHE and state in CACHE['states']:
                name = CACHE['states'][state].name
                color = CACHE['states'][state].color
            else:
                name = state
                color = 'white'
        else:
            name = state['name']
            color = COLORS[state['statusCategory']['colorName']]
        super().__init__(name, color)


class JIRAUser(User):
    """JIRA User implementation."""

    def __init__(self, user):
        super().__init__(user['name'], user['emailAddress'],
                         user['displayName'])


class JIRALabel(Label):
    """JIRA Label implementation."""

    def __init__(self, label):
        # JIRA components do not have a color associated with them.
        super().__init__(label['name'], '0000ff')
        self.id = label['id']


class JIRAMilestone(Milestone):
    """JIRA Milestone implementation."""

    def __init__(self, milestone):
        super().__init__(milestone['name'], milestone['description']
                         if 'description' in milestone else '',
                         milestone['releaseDate']
                         if 'releaseDate' in milestone else None, None)


class JIRAIssueComment(IssueComment):
    """JIRA Comment implementation."""

    def __init__(self, comment, issue_url):
        super().__init__(comment['body'], JIRAUser(comment['author']),
                         comment['created'], comment['id'])
        self.issue_url = issue_url

    def url(self):
        return '%s?focusedCommentId=%s' % (self.issue_url, self.id)


class JIRAIssueEvent(IssueEvent):
    """JIRA IssueEvent implementation."""

    def __init__(self, event):
        body = []
        for item in event['items']:
            field = item['field']

            if field == 'assignee':
                if item['fromString']:
                    body.append('Assignee changed from %s to %s' %
                                (item['fromString'], item['toString']))
                else:
                    body.append('Assignee changed to %s' % item['toString'])

            if field == 'description':
                if item['fromString']:
                    body.append('Updated description')
                else:
                    body.append('Added description')

            if field == 'labels':
                if item['fromString']:
                    body.append('Removed label %s from this' %
                                item['fromString'])
                if item['toString']:
                    body.append('Added label %s to this' %
                                item['toString'])

            if field == 'priority':
                if item['fromString'] and item['toString']:
                    body.append('Priority change from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Priority %s removed' % item['fromString'])
                else:
                    body.append('Priority %s added' % item['fromString'])

            if field == 'resolution':
                if item['fromString'] and item['toString']:
                    body.append('Resolution changed from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Removed resolution %s' % item['fromString'])
                else:
                    body.append('Marked resolution as %s' % item['toString'])

            if field == 'summary':
                body += [
                    'Changed title from %(white)s{}%(reset)s to '.format(item[
                        'fromString']) +
                    '%(white)s{}%(reset)s'.format(item['toString'])
                ]

            if field == 'status':
                body.append('Moved this from %s to %s' %
                            (JIRAIssueState(item['fromString']),
                             JIRAIssueState(item['toString'])))

            if field == 'issuetype':
                body.append('Changed issue type from %s to %s' %
                            (item['fromString'], item['toString']))

            if field == 'Attachment':
                if item['fromString']:
                    body.append('Added attachment %s' % item['fromString'])
                else:
                    body.append('Removed attachment %s' % item['toString'])

            if field == 'Component':
                if item['fromString']:
                    body.append('Removed from %s component' %
                                JIRALabel(item['fromString']))
                else:
                    body.append('Added to %s component' %
                                JIRALabel(item['toString']))

            if field == 'Epic Link':
                body.append('Added this to the epic %s' % item['toString'])

            if field == 'Epic Child':
                if item['fromString']:
                    body.append('Removed %s as a child of this epic' %
                                item['fromString'])
                else:
                    body.append('Added %s as a child of this epic' %
                                item['toString'])

            if field == 'Epic Name':
                if item['fromString'] and item['toString']:
                    body.append('Changed epic name from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Set epic name to %s' % item['fromString'])
                else:
                    body.append('Removed epic name %s' % item['toString'])

            if field == 'Epic Status':
                if item['fromString'] and item['toString']:
                    body.append('Changed epic status from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Set epic status to %s' % item['fromString'])
                else:
                    body.append('Removed epic status %s' % item['toString'])

            if field == 'Fix Version':
                if item['fromString'] and item['toString']:
                    body.append('Changed milestone from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Removed this from the %s milestone' %
                                item['fromString'])
                else:
                    body.append('Added this to the %s milestone' %
                                item['toString'])

            if field == 'Flagged':
                if item['fromString'] and item['toString']:
                    body.append('Changed flag from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Removed the %s flag to this' %
                                item['fromString'])
                else:
                    body.append('Added the %s flag to this' % item['toString'])

            if field == 'Link':
                if item['fromString']:
                    body.append(item['fromString'])
                else:
                    body.append(item['toString'])

            if field == 'Parent':
                if item['fromString'] and item['toString']:
                    body.append('Change parent task from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Removed parent task %s from this' %
                                item['fromString'])
                else:
                    body.append('Added parent task %s to this' %
                                item['toString'])

            if field == 'Rank':
                body.append(item['toString'])

            if field == 'RemoteIssueLink':
                if item['fromString']:
                    body.append(item['fromString'])
                else:
                    body.append(item['toString'])

            if field == 'Sprint':
                if item['fromString'] and item['toString']:
                    body.append('Sprint changed from %s to %s' %
                                (item['fromString'], item['toString']))
                elif item['fromString']:
                    body.append('Removed this from the %s sprint' %
                                item['fromString'])
                else:
                    body.append('Added this to the %s sprint' %
                                item['toString'])

            if field == 'Workflow':
                body += [
                    'Changed workflow from %(white)s{}%(reset)s '.format(item[
                        'fromString']) +
                    'to %(white)s{}%(reset)s'.format(item['toString'])
                ]

            if not body:
                body.append(str(item))

        super().__init__('\n%(reset)s'.join(body), JIRAUser(event['author']),
                         event['created'])
