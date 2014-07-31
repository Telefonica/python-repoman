#!/usr/bin/env python
#
# Copyright 2014 Tuenti Technologies S.L.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import datetime

from hglib import util, client, templates, error, init, open, clone

# Ignore pyflakes warnings for unused imports
assert error
assert init
assert clone
assert open

# Monkeypatched to be redefined as HgClientExtensions
original_hgclient = client.hgclient

# Monkeypatch changeset template to add parents field, needed for our
# implementation of revision and parserevs
templates.changeset = (
    '{rev}\\0'
    '{node}\\0'
    '{tags}\\0'
    '{branch}\\0'
    '{author}\\0'
    '{desc}\\0'
    '{date}\\0'
    '{parents}\\0'
)


class revision(client.revision):
    def __new__(cls, rev, node, tags, branch, author, desc, date, parents):
        return tuple.__new__(
            cls, (rev, node, tags, branch, author, desc, date, parents))

    @property
    def parents(self):
        return self[7]


class HgClientExtensions(original_hgclient):
    def strip(self, changeset):
        """ Inherited method
        :func:`~repoman.repository.Repository.strip`
        """
        command_config = ["--config", "extensions.mq="]
        command = ["strip", "-r", changeset]
        self.rawcommand(command_config + command)

    @staticmethod
    def _parserevs(splitted):
        ''' splitted is a list of fields according to our rev.style, where each 6
        fields compose one revision. '''
        revs = []
        for rev in util.grouper(8, splitted):
            # truncate the timezone and convert to a local datetime
            posixtime = float(rev[6].split('.', 1)[0])
            dt = datetime.datetime.fromtimestamp(posixtime)
            revision_fields = list(rev[:7])
            revision_fields.insert(6, dt)
            revs.append(revision(*revision_fields))
        return revs

    def unbundle(self, file, update=False, ssh=None, remotecmd=None,
                 insecure=False):
        """
        Apply one or more compressed changegroup files generated by the bundle
        command.

        Returns True on success, False if an update has unresolved files.
            file - source file name
            update - update to new branch head if changesets were unbundled
            ssh - specify ssh command to use
            remotecmd - specify hg command to run on the remote side
            insecure - do not verify server certificate (ignoring web.cacerts
                       config)
        """
        args = util.cmdbuilder(
            'unbundle', file,
            u=update, e=ssh, remotecmd=remotecmd, insecure=insecure)
        eh = util.reterrorhandler(args)
        self.rawcommand(args, eh=eh)

        return bool(eh)

    def churn(self, revrange=None, date=None, template=None, dateformat=None,
              files=[], changesets=False,
              sort=None, include=None, exclude=None):
        """
        histogram of changes to the repository

        This command will display a histogram representing the number of
        changed lines or revisions, grouped according to the given template.
        The default template will group changes by author. The --dateformat
        option may be used to group the results by date instead.

        Statistics are based on the number of changed lines, or alternatively
        the number of matching revisions if the --changesets option is
        specified.

        Examples:

          # display count of changed lines for every committer
          hg churn -t '{author|email}'

          # display daily activity graph
          hg churn -f '%H' -s -c

          # display activity of developers by month
          hg churn -f '%Y-%m' -s -c

          # display count of lines changed in every year
          hg churn -f '%Y' -s

        It is possible to map alternate email addresses to a main address by
        providing a file using the following format:

          <alias email> = <actual email>

        Such a file may be specified with the --aliases option, otherwise a
        .hgchurn file will be looked for in the working directory root.

        revrange          count rate for the specified revision or range
        date              count rate for revisions matching date spec
        template TEMPLATE  to group changesets (default: {author|email})
        dateformat FORMAT strftime-compatible format for grouping by date
        changesets count rate by number of changesets
        sort sort by key (default: sort by count)
        include include names matching the given patterns
        exclude  exclude names matching the given patterns
        """
        args = util.cmdbuilder('churn',
                               r=revrange, c=changesets, t=template,
                               f=dateformat, s=sort,
                               d=date, I=include, X=exclude, *files)
        args.extend(['--config', 'extensions.hgext.churn='])
        return self.rawcommand(args)

client.hgclient = HgClientExtensions
