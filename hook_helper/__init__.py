

import logging
import os
import time
import sys
import yaml
import subprocess



def setup_loggger():
    # sanity check
    if 'GITGLUE_LOG_DIR' not in os.environ:
        raise KeyError("Require environment variable to be set: GITGLUE_LOG_DIR")
    if not os.path.isdir(os.environ['GITGLUE_LOG_DIR']):
        raise FileNotFoundError("Log directory not found: {}".format(os.environ['GITGLUE_LOG_DIR']))
    log_file = '{:.06f}_{}'.format(time.time(), sys.argv[0].split('/')[-1])
    # create log file
    logging.basicConfig(
        filename=os.path.join(os.environ['GITGLUE_LOG_DIR'], log_file),
        format='%(created)f [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)',
        level=logging.DEBUG,
    )
    logging.info("start log: %s", sys.argv[0])


def load_config():
    """Load the config file specified in uwsgi environment GITGLUE_CONFIG

    :return: config contents (should be dict)
    """
    if 'GITGLUE_CONFIG' not in os.environ:
        raise KeyError("Require environment variable to be set: GITGLUE_CONFIG")
    config_path = os.environ['GITGLUE_CONFIG']
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



class GitWrapper(object):
    """Run git commands and process output for programatic use
    """
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

