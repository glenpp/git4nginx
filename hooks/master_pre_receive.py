#!/usr/bin/env python3
"""Master pre-receive hook - symlink from repo to this

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


import os
import sys
import logging
import imp
# custom helper needs us to find the path first
sys.path.append(os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')))
import hook_helper


def log_abort(message, exit_status=1):
    print(message, file=sys.stderr)
    if exit_status is not None:
        sys.exit(exit_status)




def main(argv):
    hook_helper.setup_loggger()
    config = hook_helper.load_config()
    hook_name = argv[0].split('/')[-1]
    master_hook_dir = os.path.dirname(os.path.realpath(__file__))
    plugin_dir = hook_name.replace('-', '_') + '_plugins'
    plugin_dir = os.path.join(master_hook_dir, plugin_dir)
    # get the references list from stdin
    references = [line.strip().split(' ') for line in sys.stdin]
    # prepare plugin info
    if 'REMOTE_USER' not in os.environ:
        hook_helper.log_abort("No REMOTE_USER in environment")
    username = os.environ['REMOTE_USER']
    if username not in config['authentication']:
        hook_helper.log_abort("User %s not in authentication config", username)
    user_authentication = config['authentication'][username]
    groups = user_authentication['groups'] if 'groups' in user_authentication else []
    inputs = [argv, references]
    gitwrapper = hook_helper.GitWrapper()
    # load & run plugins
    for plugin_file in sorted(os.listdir(plugin_dir)):
        logging.debug(plugin_file)
        plugin_name, ext = os.path.splitext(plugin_file)
        if ext != '.py':
            continue
        if '.' + plugin_name not in config['hooks']:  # TODO needs to search for this repo, check enabled
            # plugin name not enabled
            continue
        plugin_config = config['hooks']['.' + plugin_name]    # TODO needs to search for this repo
        logging.info("Loading plugin: %s", plugin_name)
        info = imp.find_module(plugin_name, [plugin_dir])
        plugin = imp.load_module(plugin_name, *info)
        logging.info("Executing plugin: %s", plugin_name)
        plugin_obj = plugin.Plugin(
            username,
            groups,
            user_authentication,
            plugin_config,
            config,
            inputs,
            gitwrapper
        )
        plugin_obj.run()




if __name__ == '__main__':
    main(sys.argv)
