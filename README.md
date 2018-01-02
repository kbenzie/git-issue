git-issue(1) -- Manage remote Git issue trackers
================================================

## SYNOPSIS

`git issue` \[`-h`\]  
`git issue create` \[`-m`\] \[`-a`\] \[`-s`\] \[`-l`\]  
`git issue edit` \[`-m`\] \[`-n`\] \[`-a`\] \[`-s`\] \[`-l`\] _number_  
`git issue close` \[`-m`\] \[`-n`\] _number_  
`git issue reopen` _number_  
`git issue comment` \[`-m`\] _number_  
`git issue browse` \[`-u`\] _number_  
`git issue list` \[`--oneline`\] \[{_open_,_closed_,_all_}\]  
`git issue show` \[`--summary`\] _number_  

## DESCRIPTION

`git-issue` provides a command line interface to remote issue trackers allowing
users to manage issues in the same way they manage git(1) repositories. A remote
issue tracker is referred to as _service_. Multiple _service_ providers can be
supported by `git-issue`, see [SERVICES](#SERVICES) for the supported _service_
list. `git-issue` determines which _service_ to use by querying `issue.service`.
Authentication with the _service_ is performed using an API token, `git-issue`
queries `issue.<service>.token` to gain access to the _service_.

## COMMANDS

* `git issue create`:
  Create a new issue, when `-m` is not specified an editor will be opened for
  the user to describe the issue.
* `git issue edit`:
  Edit an existing issue, when `-m` is not specified an editor will be opened
  for the user to edit the existing issue description.
* `git issue close`:
  Close an existing open issue, when `-n` is not specified an editor will be
  opened for the user to comment on whey the issue is being closed.
* `git issue reopen`:
  Reopen an existing closed issued.
* `git issue comment`:
  Comment on an existing issue.
* `git issue browse`:
  Open an existing issues URL in a new tab in default browser.
* `git issue list`:
  List all _open_, _closed_, or _all_ existing issues, output is paged using
  less(1).
* `git issue show`:
  Show an existing issue, including comments and state changes, output is paged
  using less(1).

## OPTIONS

* `-h`, `--help`:
  Show this manual and exit.
* `-m` _message_, `--message` _message_:
  Use the given _message_ as the issue title, editor will not be opened to edit
  a message, is mutually exclusive with `-n`.
* `-n`, `--no-message`:
  Do not open the editor to edit a message, is mutually exclusive with `-m`.
* `-a` _assignee_, `--assignee` _assignee_:
  Search term for a user to assign the issue to.
* `-s` _milestone_, `--milestone` _milestone_:
  Name of the _milestone_ to assign to the issue or _none_ to remove existing
  milestone.
* `-l` _label_, `--label` _label_:
  Name of a _label_ to assign to the issue, can be repeated to assign multiple
  _label_'s to the issue or _none_ to remove existing labels.
* _number_:
  The issue number to manage, the actual representation may change dependant on
  configured service.
* _open_, _closed_, _all_:
  The current state of issues to list, if the default is _open_.
* `--summary`:
  Print issue summary only, only available for `git issue show`.
* `--oneline`:
  Print each issue on one line, only available for `git issue list`.

## SERVICES

* `GitHub`:
  To enable this service set `issue.service` to `GitHub` and
  `issue.GitHub.token` to `<username>`_:_`<token>` replacing `<username>` with
  your GitHub login and `<token>` with a [personal access token][github-token].
* `Gogs`:
  To enable this service set `issue.service` to `Gogs` and `issue.Gogs.token` to
  `<token>` created at `https://your.gogs.url/user/settings/applications`.

## SYNTAX

The syntax of editor message is dependant on the service providing the issue
tracker, by default this will be [Markdown][markdown] or some variation of it
i.e. [GitHub Flavoured Markdown][github-markdown]. `git-issue` generally does
not process the text input by the user, with one exception; when editing a
message in the editor the second line in the file will be ignored as a separator
between the _title_ and _body_ of the issue.

## ENVIRONMENT

`git-issue` takes advantage of git-config(1) to store information which it
requires to function.

* _git config_ `issue.service` _service_:
  Name of the service which provides the remote issue tracker, e.g. `Gogs`.
* _git config_ `issue.<service>.url` _url_:
  HTTP URL of the service providing the remote issue tracker, `git-issue` will
  attempt to deduce this value if it is not set by inspecting the repositories
  remote URL and is thus not usually required to be manually configured.
  `<service>` must be replaced with name of the configured service, e.g. `Gogs`.
* _git config_ `issue.<service>.token` _token_:
  The user API token for the configured remote issue tracker, this can be
  usually be acquired through the web interface. `<service>` must be replaced
  with name of the configured service, e.g. `Gogs`.
* _git config_ `issue.<service>.remote` _remote_:
  By default `git-issue` uses `origin` when attempting to determine the HTTP URL
  of a service, if `origin` does not point to the remote issue tracker setting
  _remote_ will override the default behaviour. `<service>` must be replaced
  with name of the configured service, e.g. `Gogs`.

`git-issue` attempts to determine which editor to use when editing messages in
the same way as git(1), following are the steps taken to determine which editor
to use.

* _git config --get_ `core.editor`:
  This is the first choice and is the same editor as used for git-commit(1)
  messages.
* `EDITOR`:
  If `core.editor` is not set then the `EDITOR` environment variable is
  inspected.
* _vi_:
  Finally if neither of the above are set `git-issue` falls back to using the
  venerable vi(1) editor.

## RETURN VALUES

* `0`:
  Success, no error occurred.

* `1`:
  Failure, a fatal error has occurred.

* `130`:
  Failure, user interrupt has occurred.

Any other error codes are propagated from the underlying command, i.e.
git-config(1).

## COMPLETIONS

`git-issue` provides zsh(1) completions by default, the completions are
installed relative to the command line tool in `share/zsh/site-functions`. If
the install went as expected these should be available next time `compinit` is
invoked, however if completions are not working check please check that the
`_git-issue` file resides in a directory in the `fpath` array, refer to
zshbuiltins(1) and zshcompsys(1) for more information.

## SECURITY CONSIDERATIONS

`git-issue` relies on service API tokens to be stored in git-config(1) files,
ensure that these files have appropriate permissions and that the system is
secure (password protected) when not attended to avoid data loss or destructive
activities occurring in your absence.

## BUGS

* `Gogs` does not reliably support repeatedly editing _labels_, a warning will
  be emitted if this is attempted.

Please report any issues on [GitHub][issues].

## HISTORY

0.2.8 - Enable removal of labels/milestone.

0.2.7 - Display message on command success.

0.2.6 - Add options for concise output.

0.2.5 - Add support for editing Gogs issue labels.

0.2.4 - Respect `issue.<service>.url` when set.

0.2.3 - Move generated documentation to docs.

0.2.2 - Fix pip install & service instantiation.

0.2.1 - Fix zsh(1) completions install location.

0.2.0 - Support `GitHub` service.

0.1.3 - Refactor in preparation for additional services.

0.1.2 - Fix install of data files in setup.py.

0.1.1 - Fix bug in git issue comment.

0.1.0 - Support `Gogs` service.

## AUTHOR

Kenneth Benzie

## COPYRIGHT

MIT License

Copyright 2017 Kenneth Benzie

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## SEE ALSO

git(1) git-config(1) git-commit(1) less(1) zsh(1) zshbuiltins(1) zshcompsys(1)

[github-token]: https://github.com/settings/tokens
[markdown]: https://daringfireball.net/projects/markdown/syntax
[github-markdown]: https://github.github.com/gfm/
[issues]: https://github.com/kbenzie/git-issue/issues
