"""Hook plugin - protect branches from writes without permission

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
        """Execute the plugin - ensure permission to write to branches
        """
        for rev in self.revisions:
            head = rev[2]
            if not head.startswith('refs/heads/'):
                hook_helper.log_abort("Unexpected refernce: {}".format(head))
            branch = head.split('/')[-1]
            if 'branches' not in self.plugin_config:
                hook_helper.log_abort("Config missing: branches")

            # check if a branch is configured (restricted)
            branch_config = self.plugin_config['branches']
            if branch not in branch_config:
                logging.info("non-restricted branch, allowed to write to: %s", branch)
                continue
            # check if write permission TODO
            branch_config = branch_config[branch]
            print(self.groups)
            print(branch_config)
            if '.write_groups' in branch_config and not self.groups.isdisjoint(set(branch_config['.write_groups'])):
                logging.info("Group allowed to write to: %s", branch)
                continue
            if '.write_users' in branch_config and self.username in branch_config['.write_users']:
                logging.info("User allowed to write to: %s", branch)
                continue
            # failed to get permission - STOP
            message = "Neither groups or user has permission to write to restricted branch: {}".format(branch)
            print(message)
            hook_helper.log_abort(message)
