#!/usr/bin/env python3
"""Master pre-receive hook - symlink from repo to this

git4nginx tools for using git via http(s) with Nginx
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
import json
import imp
# custom helper needs us to find the path first
sys.path.append(os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')))
import hook_helper



def main(argv):
    """Main entry point for hook

    :argv: list, arguments passed to hook
    """
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
        hook_helper.log_abort("No REMOTE_USER in environment")  # TODO more serious
    username = os.environ['REMOTE_USER']
    if 'GIT4NGINX_GROUPS' not in os.environ:
        hook_helper.log_abort("No GIT4NGINX_GROUPS in environment") # TODO more serious
    groups = set(json.loads(os.environ['GIT4NGINX_GROUPS']))
    if 'GIT4NGINX_INFO' not in os.environ:
        hook_helper.log_abort("No GIT4NGINX_INFO in environment")   # TODO more seriouis
    user_info = set(json.loads(os.environ['GIT4NGINX_INFO']))
    inputs = [argv, references]
    gitwrapper = hook_helper.GitWrapper()
    project_group, project = hook_helper.repo_parts(config['repo_root'])
    # process each plugin that is enabled
    for plugin_file in sorted(os.listdir(plugin_dir)):
        logging.debug(plugin_file)
        plugin_name, ext = os.path.splitext(plugin_file)
        if ext != '.py':
            continue
        # calculate specific project config
        plugin_config_key = '.' + plugin_name
        plugin_config = None
        if plugin_config_key in config['hooks']:
            # global - all projects
            plugin_config = config['hooks'][plugin_config_key]
        if project_group in config['hooks']:
            if plugin_config_key in config['hooks'][project_group]:
                # project group - all projects in group
                plugin_config = config['hooks'][project_group][plugin_config_key]
            if project in config['hooks'][project_group]:
                if plugin_config_key in config['hooks'][project_group][project]:
                    # project specific config
                    plugin_config = config['hooks'][project_group][project][plugin_config_key]
        if plugin_config is None:
            # plugin not configured
            continue
        if 'enable' in plugin_config and not plugin_config['enable']:
            # plugin disabled
            continue
        # load and run the plugin
        logging.info("Loading plugin: %s", plugin_name)
        # catch any exceptions for the plugin
        try:
            info = imp.find_module(plugin_name, [plugin_dir])
            plugin = imp.load_module(plugin_name, *info)
            logging.info("Executing plugin: %s", plugin_name)
            plugin_obj = plugin.Plugin(
                username,
                groups,
                user_info,
                plugin_config,
                config,
                inputs,
                project_group, project,
                gitwrapper
            )
            plugin_obj.run()
        except Exception as exc:
            logging.error("Exception in plugin: %s", exc.__class__.__name__, exc_info=True)
            sys.exit("Hook failed")




if __name__ == '__main__':
    main(sys.argv)
