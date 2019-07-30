#!/usr/bin/env python3
"""Universal hook - symlink everything to this

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
import yaml
import subprocess


class GitWrapper(object):
    zero = '0000000000000000000000000000000000000000'

    def __init__(self, git_dir):
        self.git_dir = os.path.realpath(git_dir)
        self.git_command = ['git', '--git-dir={}'.format(self.git_dir)]

    def get_revisions(self, revision_range):
        log_output = subprocess.check_output(self.git_command + ['log', '--pretty=oneline', revision_range])
        revisions = [log.split(b' ')[0].decode('ascii') for log in log_output.splitlines()]
        return revisions
        # for checking rev in branch:
        #   44f15621ecf9ee860ec7ac3ea422c002c296f35f^..master
        #       no output with rev not in branch
        #   44f15621ecf9ee860ec7ac3ea422c002c296f35f^..dev
        #       output from this ref with rev in branch


def log_abort(message, exit_status=1):
    print(message, file=sys.stderr)
    if exit_status is not None:
        sys.exit(exit_status)

def load_config():
    """Load the config file specified in uwsgi environment GITWRAPPER_CONFIG

    :return: config contents (should be dict)
    """
    if '_GITWRAPPER_CONFIG' not in os.environ:
        raise KeyError("Require environment variable to be set: _GITWRAPPER_CONFIG")
    config_path = os.environ['_GITWRAPPER_CONFIG']
    # read config
    try:
        with open(config_path, 'rt') as f_conf:
            config = yaml.safe_load(f_conf)
    except FileNotFoundError:
        log_abort("Configuration file not found: {}".format(config_path))
    except yaml.parser.ParserError as exc:
        log_abort("Configuration file yaml error:\n{}".format(exc))
    # sanity check config
    if 'authentication' not in config or not isinstance(config['authentication'], dict):
        log_abort("Configuration file does not contain 'authentication' map")
    if 'authorisation' not in config or not isinstance(config['authorisation'], dict):
        log_abort("Configuration file does not contain 'authorisation' map")
    # TODO more checks
    return config


def main(argv):
    config = load_config()
    # work out main hook dir
    repo = os.getcwd()
    hook_name = os.path.basename(argv[0])
    master_hook = os.path.realpath(argv[0])
    hook_dir = os.path.dirname(master_hook)
    plugins_dir = os.path.join(hook_dir, 'plugins')
    # setup for plugins
    git = GitWrapper(repo)
    # TODO probably want to resolve user and groups from REMOTE_USER
    # TODO work out what plugins apply to this repo


    # TODO proxy to user_hooks/
    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv)
