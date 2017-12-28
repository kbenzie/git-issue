"""Command line interface for git-issue."""

from __future__ import print_function

import warnings
from argparse import SUPPRESS, ArgumentParser
from os import environ, remove
from os.path import join
from subprocess import (PIPE, CalledProcessError, Popen, check_call,
                        check_output)
from sys import stderr, stdout
from webbrowser import open_new_tab

from colorama import Fore
from git_issue import GitIssueError, get_service
from git_issue.service import IssueComment, IssueEvent
from pick import pick


def _warn_(message):
    print(
        '%(yellow)swarning:%(reset)s %(message)s' % {
            'yellow': Fore.YELLOW,
            'reset': Fore.RESET,
            'message': message
        },
        file=stderr)


def _error_(message):
    print(
        '%(red)serror:%(reset)s %(message)s' % {
            'red': Fore.RED,
            'reset': Fore.RESET,
            'message': message
        },
        file=stderr)
    exit(1)


def _git_dir_():
    return check_output(['git', 'rev-parse', '--git-dir']).strip()


def _hex_to_term_(color):
    def _quantize_(color):
        if color <= 0x40:
            color = 0
        elif color <= 0x80 or color < 0xbf:
            color = 0x80
        elif color <= 0xff:
            color = 0xff
        return color

    def _normalize_(color, upper):
        if color[0] == upper or color[1] == upper or color[2] == upper:
            if color[0] != upper:
                color[0] = 0
            if color[1] != upper:
                color[1] = 0
            if color[2] != upper:
                color[2] = 0
        return color

    color = [
        _quantize_(color.red), _quantize_(color.green), _quantize_(color.blue)
    ]
    color = _normalize_(color, 0xff)
    color = _normalize_(color, 0x80)

    return {
        (0x00, 0x00, 0x00): Fore.RESET,  # NOTE: Use terminal default for black
        (0x00, 0x00, 0x80): Fore.BLUE,
        (0x00, 0x80, 0x00): Fore.GREEN,
        (0x00, 0x80, 0x80): Fore.CYAN,
        (0x80, 0x00, 0x00): Fore.RED,
        (0x80, 0x00, 0x80): Fore.MAGENTA,
        (0x80, 0x80, 0x00): Fore.YELLOW,
        (0x80, 0x80, 0x80): Fore.LIGHTBLACK_EX,
        (0x00, 0x00, 0xff): Fore.LIGHTBLUE_EX,
        (0x00, 0xff, 0x00): Fore.LIGHTGREEN_EX,
        (0x00, 0xff, 0xff): Fore.LIGHTCYAN_EX,
        (0xff, 0x00, 0x00): Fore.LIGHTRED_EX,
        (0xff, 0x00, 0xff): Fore.LIGHTMAGENTA_EX,
        (0xff, 0xff, 0x00): Fore.LIGHTYELLOW_EX,
        (0xff, 0xff, 0xff): Fore.LIGHTWHITE_EX,
    }[tuple(color)]


def _pick_user_(service, keyword):
    if keyword:
        users = service.user_search(keyword)
        if len(users) > 1:
            user, _ = pick([
                u'%s' % user for user in users
            ], 'Choose from multiple matches for: %s (select then press Enter)'
                           % keyword)
            return user
        else:
            return users[0]


def _check_labels_(service, labels):
    checked = []
    if labels:
        service_labels = {label.name: label for label in service.labels()}
        for label in labels:
            if label not in service_labels:
                raise GitIssueError('invalid label name: %s' % label)
            checked.append(service_labels[label])
    return checked


def _check_milestone_(service, milestone):
    checked = None
    if milestone:
        service_milestones = {milestone.title: milestone
                              for milestone in service.milestones()}
        if milestone in service_milestones:
            checked = service_milestones[milestone]
    return checked


def _editor_(template='\n'):
    try:
        editor = check_output(
            ['git', 'config', '--get', 'core.editor']).strip()
    except CalledProcessError:
        editor = environ.get('EDITOR', None)
    if not editor:
        editor = 'vi'
    path = join(_git_dir_(), 'ISSUEMSG')
    with open(path, 'w') as issuemsg:
        issuemsg.write(template)
    check_call(
        [editor, '+setfiletype markdown' if 'vim' in editor else '', path])
    with open(path, 'r') as issuemsg:
        message = issuemsg.read().splitlines()
        if len(message) == 0:
            raise GitIssueError('aborted due to empty message')
    remove(path)
    return message


def _pager_(content):
    if stdout.isatty:
        process = Popen(['less', '-F', '-R', '-X', '-K'], stdin=PIPE)
        try:
            process.stdin.write(content)
            process.communicate()
        except IOError:
            print(content)
    else:
        print(content)


def _state_color_(state):
    return {'open': Fore.GREEN,
            'reopened': Fore.GREEN,
            'closed': Fore.RED}[state]


def _human_date_(date):
    return date.format('ddd MMM DD HH:mm:ss YYYY ZZ')


def _issue_state_(issue):
    state = '%(color)s%(state)s%(yellow)s' % {
        'color': _state_color_(issue.state),
        'state': issue.state,
        'yellow': Fore.YELLOW
    }
    if issue.milestone:
        state += ' %s' % issue.milestone.title
    if len(issue.labels) > 0:
        state += ' ' + ' '.join(['%(color)s%(label)s%(yellow)s' %
                                 {'color': _hex_to_term_(label.color),
                                  'label': label.name,
                                  'yellow': Fore.YELLOW}
                                 for label in issue.labels])
    return state


def _issue_summary_(issue, num_comments=0):
    title = '%(yellow)s%(number)s %(title)s' % {'yellow': Fore.YELLOW,
                                                'number': issue.number,
                                                'title': issue.title}
    output = [
        '%(title)s (%(state)s)%(reset)s' % {'title': title,
                                            'state': _issue_state_(issue),
                                            'reset': Fore.RESET},
        'Author:   %s' % issue.author,
    ]
    if issue.assignee:
        output.append('Assignee: %s' % issue.assignee)
    output.append('Date:     %s' % _human_date_(issue.created))
    if len(issue.body) > 0:
        output.append('')
        output += ['    %s' % line for line in issue.body.splitlines()]
    if num_comments > 0:
        output.append('')
        output.append('%s comment%s' % (num_comments, 's'
                                        if num_comments > 1 else ''))
    return output


def _finish_(action, number, url):
    print('%(color)s%(action)s%(reset)s issue %(number)s: %(url)s' %
          {'color': {
              'Created': Fore.GREEN,
              'Edited': Fore.YELLOW,
              'Commented on': Fore.RESET,
              'Closed': Fore.RED,
              'Reopened': Fore.GREEN,
          }[action],
           'action': action,
           'reset': Fore.RESET,
           'number': number,
           'url': url})
    exit(0)


def create(service, **kwargs):
    """Create a new issue."""
    assignee = _pick_user_(service, kwargs.pop('assignee', None))
    milestone = _check_milestone_(service, kwargs.pop('milestone', None))
    labels = _check_labels_(service, kwargs.pop('labels', None))
    if kwargs['message']:
        message = kwargs.pop('message').splitline().split('\\n')
    else:
        message = _editor_('\n'.join([
            '',
            '<!-- This line will be ignored! Title above, body below. -->',
            '',
            '',
        ]))
        del message[1]
    title = message[0]
    body = '\n'.join(message[1:]) if len(message) > 1 else ''
    if len(title.strip()) == 0 and len(body.strip()) == 0:
        raise GitIssueError('aborting due to empty message')
    issue = service.create(
        title, body, assignee=assignee, labels=labels, milestone=milestone)
    _finish_('Created', issue.number, issue.url())


def edit(service, **kwargs):
    """Edit an existing issue."""
    issue = service.issue(kwargs.pop('number'))
    assignee = _pick_user_(service, kwargs.pop('assignee', None))
    milestone = _check_milestone_(service, kwargs.pop('milestone', None))
    labels = _check_labels_(service, kwargs.pop('labels', None))
    if kwargs['no_message']:
        title = None
        body = None
    else:
        if kwargs['message']:
            message = kwargs.pop('message').splitlines().split('\\n')
        else:
            message = _editor_('\n'.join([
                issue.title,
                '<!-- This line will be ignored! Title above, body below. -->',
                issue.body,
            ]))
            del message[1]
        title = message[0] if message[0] != issue.title else None
        body = '\n'.join(message[1:]) if len(message) > 1 else None
    issue.edit(
        title=title,
        body=body,
        assignee=assignee,
        labels=labels,
        milestone=milestone)
    _finish_('Edited', issue.number, issue.url)


def comment(service, **kwargs):
    """Comment on an existing issue."""
    issue = service.issue(kwargs.pop('number'))
    if kwargs['message']:
        body = kwargs.pop('message')
    else:
        body = '\n'.join(_editor_())
    if len(body.strip()) == 0:
        raise GitIssueError('aborted due to empty message')
    comment = issue.comment(body)
    _finish_('Commented on', '%s' % issue.number, comment.url())


def close(service, **kwargs):
    """Close an existing open issue."""
    issue = service.issue(kwargs.pop('number'))
    if issue.state != 'open':
        raise GitIssueError('issue %s is not open' % issue.number)
    comment = None
    if not kwargs['no_message']:
        if kwargs['message']:
            comment = kwargs.pop('message')
        else:
            comment = '\n'.join(_editor_())
        if len(comment.strip()) == 0:
            raise GitIssueError('aborted due to empty message')
    issue = issue.close(comment=comment)
    _finish_('Closed', issue.number, issue.url())


def reopen(service, **kwargs):
    """Reopen an existing closed issue."""
    issue = service.issue(kwargs.pop('number'))
    if issue.state != 'closed':
        raise GitIssueError('issue %s is not closed' % issue.number)
    issue = issue.reopen()
    _finish_('Reopened', issue.number, issue.url())


def show(service, **kwargs):
    """Show detail of a single issue."""
    issue = service.issue(kwargs.pop('number'))
    summary = kwargs.pop('summary')
    output = _issue_summary_(issue, issue.num_comments if summary else 0)
    if not summary:
        for item in sorted(issue.comments() + issue.events()):
            if isinstance(item, IssueComment):
                output += [
                    '',
                    'Comment:  %s' % item.author,
                    'Date:     %s' % _human_date_(item.created),
                    '',
                ]
                output += ['    %s' % line for line in item.body.splitlines()]
            elif isinstance(item, IssueEvent):
                output += [
                    '',
                    '%(color)s%(state)s%(reset)s%(user)s' % {
                        'color': _state_color_(item.event),
                        'state': ('%s:' % item.event.capitalize()).ljust(10),
                        'reset': Fore.RESET,
                        'user': item.actor,
                    },
                    'Date:     %s' % _human_date_(item.created),
                ]
    _pager_('\n'.join(output))
    exit(0)


def list(service, **kwargs):
    """List existing issues."""
    output = []
    issues = service.issues(kwargs.pop('state'))
    if kwargs.pop('oneline'):
        for issue in issues:
            output.append(
                '%(yellow)s%(number)s (%(state)s)%(reset)s %(title)s' % {
                    'yellow': Fore.YELLOW,
                    'number': issue.number,
                    'state': _issue_state_(issue),
                    'reset': Fore.RESET,
                    'title': issue.title,
                })
    else:
        for issue in issues:
            output += _issue_summary_(issue, issue.num_comments)
            output.append('')
    _pager_('\n'.join(output))
    exit(0)


def browse(service, **kwargs):
    """Show issue in detault browser."""
    issue = service.issue(kwargs.pop('number'))
    if kwargs['url']:
        print(issue.url())
    else:
        open_new_tab(issue.url())
    exit(0)


def complete(service, **kwargs):
    """Provide completions."""
    complete_type = kwargs.pop('type')
    if complete_type == 'issues':
        state = kwargs.pop('state', 'open')
        issues = service.issues(state)
        if 'zsh' in environ['SHELL']:
            # In zsh display the issue title as the description
            output = '\n'.join(['%r:%s' % (issue.number, issue.title)
                                for issue in issues])
        else:
            # Otherwise just supply the issue number
            output = '\n'.join(['%r' % issue.number for issue in issues])
    if complete_type == 'labels':
        output = '\n'.join(['%s' % label.name for label in service.labels()])
    if complete_type == 'milestones':
        output = '\n'.join(
            [milestone.title for milestone in service.milestones()])
    print(output, end='')
    exit(0)


def main():
    """Main entry point."""
    try:
        warnings.showwarning = lambda *args: _warn_(args[0].message)

        parser = ArgumentParser()
        parser.add_argument(
            '-d', '--debug', action='store_true', help=SUPPRESS)
        subparsers = parser.add_subparsers()

        create_parser = subparsers.add_parser('create')
        create_parser.set_defaults(_command_=create)
        create_parser.add_argument('-m', '--message')
        create_parser.add_argument('-a', '--assignee')
        create_parser.add_argument('-s', '--milestone')
        create_parser.add_argument(
            '-l', '--label', action='append', dest='labels')

        edit_parser = subparsers.add_parser('edit')
        edit_parser.set_defaults(_command_=edit)
        edit_group = edit_parser.add_mutually_exclusive_group()
        edit_group.add_argument('-m', '--message')
        edit_group.add_argument('-n', '--no-message', action='store_true')
        edit_parser.add_argument('-a', '--assignee')
        edit_parser.add_argument('-s', '--milestone')
        edit_parser.add_argument(
            '-l', '--label', action='append', dest='labels')
        edit_parser.add_argument('number')

        comment_parser = subparsers.add_parser('comment')
        comment_parser.set_defaults(_command_=comment)
        comment_parser.add_argument('-m', '--message')
        comment_parser.add_argument('number')

        close_parser = subparsers.add_parser('close')
        close_parser.set_defaults(_command_=close)
        close_parser.add_argument('-m', '--message')
        close_parser.add_argument('-n', '--no-message', action='store_true')
        close_parser.add_argument('number')

        reopen_parser = subparsers.add_parser('reopen')
        reopen_parser.set_defaults(_command_=reopen)
        reopen_parser.add_argument('number')

        show_parser = subparsers.add_parser('show')
        show_parser.set_defaults(_command_=show)
        show_parser.add_argument('--summary', action='store_true')
        show_parser.add_argument('number')

        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(_command_=list)
        list_parser.add_argument('--oneline', action='store_true')
        list_parser.add_argument(
            'state',
            choices=['open', 'closed', 'all'],
            default='open',
            nargs='?')

        browse_parser = subparsers.add_parser('browse')
        browse_parser.set_defaults(_command_=browse)
        browse_parser.add_argument('-u', '--url', action='store_true')
        browse_parser.add_argument('number', nargs='?')

        complete_parser = subparsers.add_parser('complete')
        complete_parser.set_defaults(_command_=complete)
        complete_parser.add_argument(
            'type', choices=['issues', 'labels', 'milestones'])
        complete_parser.add_argument(
            '--state', choices=['all', 'open', 'closed'])

        args = vars(parser.parse_args())
        debug = args.pop('debug')
        command = args.pop('_command_')
        command(get_service(), **args)
    except GitIssueError as error:
        if debug:
            from sys import exc_info
            from traceback import print_exception
            exc_type, exc_value, exc_traceback = exc_info()
            print_exception(exc_type, exc_value, exc_traceback)
            exit(1)
        _error_(error.message)
    except KeyboardInterrupt:
        exit(130)


if __name__ == '__main__':
    main()
