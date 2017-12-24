git-issue - Manage remote git issue trackers
============================================

`git-issue <https://kbenzie.github.io/git-issue>`_ provides a command line
interface to remote issue trackers allowing users to manage issues in the same
way they manage `git <https://git-scm.com/>`_ repositories. A remote issue
tracker is referred to as *service*. Multiple *service* providers can be
supported by `git-issue <git-issue_>`_, see `SERVICES
<https://kbenzie.github.io/git-issue#SERVICES>`_ for the supported *service*
list. `git-issue <git-issue_>`_ determines which *service* to use by querying
``issue.service``. Authentication with the *service* is performed using an API
token, `git-issue <git-issue_>`_ queries ``issue.<service>.token`` to gain
access to the *service*.

Getting Started
---------------

Follow the steps below to setup a working `git-issue <git-issue_>`_
installation.

Prerequisites
~~~~~~~~~~~~~

`git-issue <git-issue_>`_ is implemented in `Python <https://www.python.org>`_
and requires `pip <https://pypi.python.org/pypi/pip>`_ for installation.

Installing
~~~~~~~~~~

To install `git-issue <git-issue_>`_ globally execute the following command,
``sudo`` may be required on your system:

::

    $ [sudo] pip install git-issue

Alternatively, to install only for the current user:

::

    $ pip install --user git-issue

User installs are installed with a platform specifc prefix, to ensure
`git-issue <git-issue_>`_ can be used correctly a few environment variables
must be set to include this prefix:

::

    $ prefix=`python -c 'import site; import sys; sys.stdout.write(site.USER_BASE)'`

To ensure the `git-issue <git-issue_>`_ command is available for user installs
add the following to the ``PATH`` environment variable.

::

    $ export PATH=$prefix/bin:$PATH

To ensure the `git-issue <git-issue_>`_ man page can be found for ``git issue
--help`` for user installs add the following to the ``MANPATH`` environment
variable:

::

    $ export MANPATH=$prefix/share/man:$MANPATH

To ensure Zsh completions for `git-issue <git-issue_>`_ can be found for user
installs add the following to the ``fpath`` array variable:

::

    $ fpath+=$prefix/share/zsh/site-functions

..

    NOTE: It is desirable to set these variables in your shells config files.

Usage
~~~~~

Example of cloning a repository, configuring `git-issue <git-issue_>`_, and
listing *all* its issues.

::

    $ git clone https://github.com/kbenzie/git-issue.git
    $ cd git-issue
    $ git config issue.service GitHub
    $ git config issue.GitHub.token <your-login>:<your-personal-access-token>
    $ git issue list all

For further information see the manual ``git issue --help``.

Authors
-------

`Kenneth Benzie <benie@infektor.net>`_.

License
-------

This project is licensed under the `MIT License <LICENSE.md>`_.
