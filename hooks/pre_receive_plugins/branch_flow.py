"""Hook plugin - ensure change flow through branches

git-glue tools for using git via http(s) with Nginx
Copyright (C) 2019  Glen Pitt-Pladdy

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""


import logging
import hook_helper


class Plugin(object):
    run_hooks = [
        'pre-receive',
    ]
    def __init__(self, username, groups, user_info, plugin_config, config, inputs, project_group, project, gitwrapper):
        """Common setup for plugin
        """
        self.username = username
        self.groups = groups
        self.user_info = user_info
        self.plugin_config = plugin_config
        self.config = config
        self.argv = inputs[0]
        self.revisions = inputs[1]
        self.project_group = project_group
        self.project = project
        self.gitwrapper = gitwrapper

    def run(self):
        """Execute the plugin - ensure revisions are in the upstream branch
        """
        for rev in self.revisions:
            head = rev[2]
            if not head.startswith('refs/heads/'):
                hook_helper.log_abort("Unexpected refernce: {}".format(head))
            branch = head.split('/')[-1]
            commit_from = rev[0]
            commit_to = rev[1]

            if branch not in self.plugin_config['flow']:
                # assume feature branch (not in restricted flow branches)
                logging.info("non-restricted branch, allowed to go into %s", branch)
                return
            flow_step = self.plugin_config['flow'].index(branch)
            if flow_step == 0:
                # starting step - good
                logging.info("starting branch, allowed to go into %s", branch)
                return

            # find what we're comparing to (prior branch in sequence)
            upstream_branch = self.plugin_config['flow'][flow_step - 1]

            # check for revision in upstream
            upstream_revisions = self.gitwrapper.get_revisions([commit_from, upstream_branch])
            if not upstream_revisions:
                message = "Upstream branch ({}) does not contain from revision for target ({}): {}".format(upstream_branch, branch, commit_from)
                print(message)
                hook_helper.log_abort(message)
            to_range = upstream_revisions if commit_from == self.gitwrapper.zero else upstream_revisions[:-1]
            if commit_to not in to_range:
                message = "Upstream branch ({}) does not contain to revision for target ({}): {}".format(upstream_branch, branch, commit_to)
                print(message)
                hook_helper.log_abort(message)
            # revisions are in upstream branch so we seem to be good
            logging.info("%s..%s found in %s, allowed to go into %s", commit_from, commit_to, upstream_branch, branch)
