#!/usr/bin/env python3
"""Universal hook - symlink everything to this
"""


import os
import sys


def main(argv):
    # work out config location
    if '_GITWRAPPER_CONFIG' not in os.environ:
        raise KeyError("Require environment variable to be set: _GITWRAPPER_CONFIG")
    config_path = os.environ['_GITWRAPPER_CONFIG']
    # TODO check and read config
    # work out main hook dir
    repo = os.getcwd()
    master_hook = os.path.realpath(argv[0])
    hook_dir = os.path.dirname(master_hook)
    plugins_dir = os.path.join(hook_dir, 'plugins')
    # TODO work out what plugins apply to this repo


    # TODO proxy to user_hooks/
    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv)
