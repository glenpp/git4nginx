"""Minimal git http wrapper for Nginx with uwsgi

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

import logging
import re
import tempfile
import subprocess
import imp
import os
import json
import base64
import yaml
import select
import fcntl



import flask
app = flask.Flask(__name__)
## for this app config must be loaded here before it's used for module paths below
#app.config.from_object('config')    # loads config.py
# TODO do better
# ensure our logger is used see http://y.tsutsumi.io/global-logging-with-flask.html
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d - %(message)s',
    datefmt='%c',
    #level=logging.INFO,
    level=logging.DEBUG,
)
app.logger.handlers = []
app.logger.propagate = True


@app.errorhandler(401)
def authentication_401(error):
    """Custom authentication response
    """
    return flask.Response(
        error.description,
        error.code,
        {'WWW-Authenticate': 'Basic realm="Authentication Required", charset="UTF-8"'}
    )



# repo must end .git
# may be at the top level (project_group=None)
@app.route('/<string:project>.git')
@app.route('/<string:project>.git/<path:sub_path>', methods=['GET', 'POST'])
# ... or in a sub directory (project_group)
@app.route('/<string:project_group>/<string:project>.git')
@app.route('/<string:project_group>/<string:project>.git/<path:sub_path>', methods=['GET', 'POST'])
def githandler(project, project_group=None, sub_path=None):
    """Main git http entry point

    :arg project: str, project name with .git removed
    :arg project_group: str|None, project group (directory) or None for top level
    :arg sub_path: str|None, any path elements below the repo requested
    """
    # sanity check inputs - limit these within known safe bounds
    if len(project) > 64:
        app.logger.error("Error: Project names are limited to 64 characters (before .git)")
    if not re.match(r'^[\w\-]{3,64}$', project):
        app.logger.error("Error: Project names are limited 3-64 alphanumerics, underscore '_' and hyphon '-' (before .git)")
    project += '.git'
    if project_group is not None:
        if len(project_group) > 64:
            app.logger.error("Error: Project Group names are limited to 64 characters")
        if not re.match(r'^[\w\-]{3,64}$', project_group):
            app.logger.error("Error: Project Group names are limited 3-64 alphanumerics, underscore '_' and hyphon '-'")
    # sanity checking sub_path and query based on https://www.git-scm.com/docs/http-protocol
    if flask.request.method == 'GET':
        if sub_path == 'info/refs':
            if len(flask.request.args) != 1 or 'service' not in flask.request.args:
                app.logger.critical("Unexpected query for GET %s: %s", sub_path, str(flask.request.args))
                flask.abort(400)
            if flask.request.args['service'] not in ['git-upload-pack', 'git-receive-pack']:
                app.logger.critical("Unexpected query for GET %s: %s", sub_path, str(flask.request.args))
                flask.abort(400)
        else:
            app.logger.critical("Unexpected sub_path for GET: %s", sub_path)
            flask.abort(400)
    elif flask.request.method == 'POST':
        if sub_path not in ['git-receive-pack', 'git-upload-pack']:
            app.logger.critical("Unexpected sub_path for POST: %s", sub_path)
            flask.abort(400)
    else:
        app.logger.critical("Unexpected HTTP METHOD: %s", flask.request.method)
        flask.abort(400)

    # load config
    config = load_config()
    # work out the type of operation
    is_write = False if flask.request.args.get('service') != 'git-receive-pack' and sub_path != 'git-receive-pack' else True

    # work out available authentication
    username = flask.request.remote_user
    password = None
    if username is None:
        # then we didn't get authentication from upstream so we do it ourselves
        app.logger.info("Authentication no provided from upstream so performing headers...")
        auth_header = flask.request.headers.get('authorization')
        if auth_header is None:
            app.logger.info("No authentication headers for Basic. Prompting client.")
            flask.abort(401)
        elif not auth_header.startswith('Basic '):
            app.logger.error("Authentication header does not start \"Basic\"")
            flask.abort(400)
        else:
            auth_info = base64.b64decode(auth_header[6:])
            username, password = auth_info.decode('utf-8').split(':', 1)
    # if we failed to get any user then we most likley have a configuration problem
    if username is None:
        app.logger.critical("No username can be determined for authentication. Configuration problem?")
        flask.abort(500)
    # authentication plugin
    auth_plugin_name = config['authentication']['plugin']
    app.logger.info("Loading authentication plugin: %s", auth_plugin_name)
    auth_plugin_path = os.path.dirname(os.path.realpath(__file__))
    auth_plugin_path = os.path.join(auth_plugin_path, 'authentication_plugins')
    info = imp.find_module(auth_plugin_name, [auth_plugin_path])
    auth_plugin = imp.load_module(auth_plugin_name, *info)
    app.logger.info("Checking authentication with plugin...")
    authenticated, groups, info = auth_plugin.authenticate(app.logger, config['authentication']['plugin_config'], username, password)
    if authenticated:
        authenticated_user = username
        app.logger.info("Successful authentication for user: %s", authenticated_user)
    else:
        app.logger.warning("Authentication failed for user: %s", username)
        flask.abort(401)


    # logging details for now
    app.logger.info("handler: %s %s / %s / %s", flask.request.method, project_group, project, sub_path)
    app.logger.info("        :: %s", authenticated_user)
    app.logger.info("        :: %s", groups)
    app.logger.info("        : write %s", is_write)

    # determine and log permission for this request
    permission = Permissions(config['authorisation'], authenticated_user, groups).get_permission(project_group, project)
    if permission['write'] and permission['read']:
        app.logger.info("User %s has permissions for read & write on: %s/%s", authenticated_user, project_group, project)
    elif permission['write']:
        app.logger.info("User %s has permissions for write on: %s/%s", authenticated_user, project_group, project)
    elif permission['read']:
        app.logger.info("User %s has permissions for read on: %s/%s", authenticated_user, project_group, project)
    if is_write and not permission['write']:
        app.logger.warning("User %s does not have write permission for: %s/%s", authenticated_user, project_group, project)
        flask.abort(403)
    elif not permission['read']:
        app.logger.warning("User %s does not have read permission for: %s/%s", authenticated_user, project_group, project)
        flask.abort(403)

    # sanity check repo exists
    repo_path = config['repo_root']
    if not os.path.isdir(repo_path):
        app.logger.critical("Configured repo_root does not exist: %s", repo_path)
        flask.abort(500)
    if project_group is not None:
        repo_path = os.path.join(repo_path, project_group)
    repo_path = os.path.join(repo_path, project)
    if not os.path.isdir(repo_path):
        app.logger.warning("Requested repo does not exist: %s", repo_path)
        flask.abort(404)

    # run the cgi-bin with wrapper with appropriate environment variables
    extra_env = {
        'GIT_PROJECT_ROOT': config['repo_root'],
        'GIT_HTTP_EXPORT_ALL': '',
        # user details exposed to hooks
        'REMOTE_USER': authenticated_user,  # may already be in uwsgi env
        'GIT4NGINX_GROUPS': json.dumps(groups),
        'GIT4NGINX_INFO': json.dumps(info),
    }
    if flask.request.method == 'POST':
        with HookLogDir() as temp_log_dir:
            extra_env['GIT4NGINX_LOG_DIR'] = temp_log_dir
            response = cgi_wrapper(config['bin_path'], extra_env, flask.request.stream)
        return response
    return cgi_wrapper(config['bin_path'], extra_env)





class Permissions(object):
    """Calculate permissions
    """
    def __init__(self, authorisation_config, username, groups):
        """Calculate permissions
        """
        self.authorisation_config = authorisation_config
        self.username = username
        self.user_authentication = None
        self.groups = set(groups)

    def _check_node(self, node, permission):
        """Calculate permissions for a node

        :arg node: dict, containing .read_users, .write_users, .read_groups, .write_groups
        :arg permission: dict, containing read and write keys with bool values
        :return: bool, if full permissions are gained
        """
        if '.read_users' in node:
            if self.username in node['.read_users']:
                permission['read'] = True
        if '.read_groups' in node:
            if not self.groups.isdisjoint(set(node['.read_groups'])):
                permission['read'] = True
        if '.write_users' in node:
            if self.username in node['.write_users']:
                permission['write'] = True
                permission['read'] = True # implicit
        if '.write_groups' in node:
            if not self.groups.isdisjoint(set(node['.write_groups'])):
                permission['write'] = True
                permission['read'] = True # implicit
        return permission['write'] and permission['read']


    def get_permission(self, project_group, project):
        """Calculate permissions for a request

        :arg project_group|None: str, project group being requested
        :arg project: str, project being requested
        :return: dict, containing read and write keys with bool values
        """
        permission = {
            'read': False,
            'write': False,
        }
        authorisation = self.authorisation_config
        # check project group
        if project_group not in authorisation:
            app.logger.info("Project Group no authorisation: %s", project_group)
            return permission
        authorisation = authorisation[project_group]
        if self._check_node(authorisation, permission):
            return permission
        # check project
        if project not in authorisation:
            app.logger.info("Project no authorisation: %s", project)
            return permission
        authorisation = authorisation[project]
        if self._check_node(authorisation, permission):
            return permission
        return permission



def load_config():
    """Load the config file specified in uwsgi environment GIT4NGINX_CONFIG

    :return: config contents (should be dict)
    """
    if 'GIT4NGINX_CONFIG' not in flask.request.environ:
        app.logger.critical("Configuration file not configured: GIT4NGINX_CONFIG must be in uwsgi environment")
        flask.abort(500)
    try:
        with open(flask.request.environ['GIT4NGINX_CONFIG'], 'rt') as f_conf:
            config = yaml.safe_load(f_conf)
    except FileNotFoundError:
        app.logger.critical("Configuration file not found: %s", flask.request.environ['GIT4NGINX_CONFIG'])
        flask.abort(500)
    except yaml.parser.ParserError as exc:
        app.logger.critical("Configuration file yaml error:\n%s", exc)
        flask.abort(500)
    # sanity check
    if 'authentication' not in config or not isinstance(config['authentication'], dict):
        app.logger.critical("Configuration file does not contain 'authentication' map")
        flask.abort(500)
    if 'authorisation' not in config or not isinstance(config['authorisation'], dict):
        app.logger.critical("Configuration file does not contain 'authorisation' map")
        flask.abort(500)
    return config



class HookLogDir(object):
    """Context for log directory for hooks to pass back logging
    """
    level2int = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    def __init__(self):
        """Setup
        """
        self._path = None
    def __enter__(self):
        """Enter context - create temporary directory (and store)
        """
        self._path = tempfile.mkdtemp()
        return self._path
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context - process logs in temporary directory, clean up
        """
        # re-log hook log lines
        for log in sorted(os.listdir(self._path)):
            app.logger.debug("start logfile: %s", log)
            _, hook = log.split('_', 1)
            log_path = os.path.join(self._path, log)
            with open(log_path, 'rt') as f_log:
                for line in f_log:
                    match = re.match(r'^(\d+\.\d+)\s+\[(\w+)\]\s+(\S.*)\s+\(([^\(\)]+)\)$', line.strip())
                    if not match:
                        app.logger.critical("%s - Can't parse hook log %s line: %s", hook, log, line)
                        continue
                    if match.group(2) not in self.level2int:
                        app.logger.critical("%s - Don't have a log level match for %s in line: %s", hook, match.group(2), line)
                        continue
                    level = self.level2int[match.group(2)]
                    app.logger.log(level, "%s - %s", hook, match.group(3))
            app.logger.debug("end logfile: %s", log)
            os.unlink(log_path)
        os.rmdir(self._path)



def cgi_wrapper(bin_path, extra_env=None, stream=None):
    """Run cgi translating from flask environment

    :arg bin_path: str, binary to execute
    :arg stream: stream|None, optional data stream to pass to cgi (stdin) else will pass-through
    :return: flask response
    """
    # generate execution environment
    cgienv = {
        key: value
        for key, value in flask.request.environ.items()
        if not key.startswith(('uwsgi.', 'werkzeug.', 'wsgi.'))
    }
    cgienv['SERVER_SOFTWARE'] = 'git4nginx'
    cgienv['GATEWAY_INTERFACE'] = 'CGI/1.1'
    if extra_env is not None:
        cgienv.update(extra_env)
    # execute TODO important - this will not handle large requests since everything is in memory. Needs tweaking to chunk data.
    if flask.request.method == 'GET':
        proc = subprocess.Popen(
            bin_path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=cgienv
        )
        stdout, stderr = proc.communicate()
    elif flask.request.method in ['POST', 'PUT']:
        proc = subprocess.Popen(
            bin_path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=cgienv
        )
        if stream is None:
            stdout, stderr = proc.communicate(flask.request.stream.read())
        else:
            # make outputs non-blocking
            fd = proc.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            fd = proc.stderr.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            # setup buffers
            stdout = b''
            stderr = b''
            # send data (stdin) until complete
            send_complete = False
            while proc.poll() is None and not send_complete:
                outputs, inputs, _ = select.select([proc.stdout, proc.stderr], [proc.stdin], [], 0.05)
                for output in outputs:
                    if output is proc.stdout:
                        stdout += proc.stdout.read()
                    elif output is proc.stderr:
                        stderr += proc.stderr.read()
                if inputs:
                    data = stream.read(1024)
                    if data:
                        proc.stdin.write(data)
                    else:
                        proc.stdin.close()
                        send_complete = True
            # sending complete, mop up outputs
            while proc.poll() is None:
                outputs, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.05)
                for output in outputs:
                    if output is proc.stdout:
                        stdout += proc.stdout.read()
                    elif output is proc.stderr:
                        stderr += proc.stderr.read()
            # make sure nothing is left in buffers
            stdout += proc.stdout.read()
            stderr += proc.stderr.read()
    if proc.returncode != 0:
        app.logger.debug("%s returned %s", bin_path, str(proc.returncode))
        app.logger.debug("%s stdout:\n%s\n--- end stderr", bin_path, stdout)
        app.logger.debug("%s stderr:\n%s\n--- end stderr", bin_path, stderr)
        flask.abort(500)
    elif stderr:
        app.logger.debug("%s stderr:\n%s\n--- end stderr", bin_path, stderr)
    # split and handle header from cgi
    header, body = tuple(stdout.split(b'\r\n\r\n', 1))
    status_code = 200
    headers = []
    for line in header.decode('ascii', 'ignore').splitlines():
        name, value = line.split(':', 1)
        value = value.lstrip()
        if name == 'Status':
            status_parts = value.split(' ', 1)
            status_code = int(status_parts.pop(0))
            if status_parts:
                body = status_parts[0]
        else:
            headers.append([name, value])
    # prepare response
    response = flask.Response(
        body,
        status_code
    )
    for header in headers:
        response.headers[header[0]] = header[1]
    return response
