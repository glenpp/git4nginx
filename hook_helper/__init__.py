

import logging
import os
import time
import sys
import yaml
import subprocess



def setup_loggger():
    """Prepare default logger
    """
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


def log_abort(message, exit_status=1):
    """Regular failure - log error and exit

    :arg message: str, message to log
    :arg exit_status: int, optional exit status, default 1
    """
    logging.error(message)
    if exit_status is not None:
        sys.exit(exit_status)


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
    for key in ['authentication', 'authorisation', 'hooks']:
        if key not in config or not isinstance(config[key], dict):
            log_abort("Configuration file does not contain valid '{}' configuration".format(key))
    return config



class GitWrapper(object):
    """Run git commands and process output for programatic use
    """
    zero = '0000000000000000000000000000000000000000'

    def __init__(self, git_dir=None):
        if git_dir is None:
            # assume current directory
            git_dir = os.getcwd()
        self.git_dir = os.path.realpath(git_dir)
        self.git_command = ['git', '--git-dir={}'.format(self.git_dir)]

    def git_run(self, args, stdin='', repo_path=None):
        """General case git runner

        :arg args: list, arguments to pass base git command
        :arg stdin: str, optional input to send through stdin
        :arg repo_path: str, optional path to the repo to access, else self.git_dir is used
        :return: tuple of:
            return code, int
            stdout, str
            stderr, str
        """
        if repo_path is None:
            # assume starting dir (repo)
            repo_path = self.git_dir
        git_command = [
            'git',
            '--git-dir={}'.format(repo_path),
        ]
        git_command += args
        process = subprocess.Popen(
            git_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        stdout, stderr = process.communicate(stdin)
        return process.returncode, stdout, stderr

    def is_rev_in_branch(self, revision, branch=None):
        """Checks if this the given revision exists in a branch

        :arg revision: str, revision to check
        :arg branch: str|None, check the specific branch or all if None
        """
        subprocess.check_output(
            self.git_command + [
                'branch',
                branch if branch is not None else '--all',
                '--contains', revision
            ]
        )

    def get_revisions(self, revision_range, inclusive_first=True):
        """Get a list of revisions (eg. see if range is in branch)

        :arg revision_range: str|list, if list must be 2 items
        :arg inclusive_first: bool, include the first entry (implies ^ suffix on start of range), default True
        :return: list, revisions matching, empty on failure
        """
        if isinstance(revision_range, list) and len(revision_range) == 2:
            if revision_range[0] == self.zero:
                # want to get all
                revision_range = revision_range[1]
            elif inclusive_first:
                # from change before to ensure first is included
                revision_range = '^..'.join(revision_range)
            else:
                # regular range
                revision_range = '..'.join(revision_range)
        elif not isinstance(revision_range, str):
            raise RuntimeError("Need revision_range of 2-item list or string, got %s: %s", revision_range.__class__.__name__, str(revision_range))
        status, stdout, stderr = self.git_run(['rev-list', revision_range])
        if status:
            # fail
            return []
        return [line.strip().decode('ascii') for line in stdout.splitlines()]
        # for checking rev in branch:
        #   44f15621ecf9ee860ec7ac3ea422c002c296f35f^..master
        #       no output with rev not in branch
        #   44f15621ecf9ee860ec7ac3ea422c002c296f35f^..dev
        #       output from this ref with rev in branch
        #   if starting revision is not in the branch returns non-zero => []

        # TODO
        # git rev-parse --abbrev-ref HEAD (what brances/heads are in change from stdin)
