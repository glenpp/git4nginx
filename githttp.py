"""Minimal git http wrapper for Nginx with uwsgi

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
import yaml
import re
import subprocess



import flask
app = flask.Flask(__name__)
## for this app config must be loaded here before it's used for module paths below
#app.config.from_object('config')    # loads config.py
# ensure our logger is used see http://y.tsutsumi.io/global-logging-with-flask.html
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s in %(filename)s:%(lineno)d - %(message)s',
    datefmt='%c',
#    level=logging.INFO,
    level=logging.DEBUG,
)
app.logger.handlers = []
app.logger.propagate = True




# repo must end .git
# may be at the top level (project_group=None)
@app.route('/<string:project>.git')
@app.route('/<string:project>.git/<path:sub_path>', methods=['GET', 'POST'])
# ... or in a sub directory (project_group)
@app.route('/<string:project_group>/<string:project>.git')
@app.route('/<string:project_group>/<string:project>.git/<path:sub_path>', methods=['GET', 'POST'])
def githandler(project, project_group=None, sub_path=None):
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
                app.logger.critical("Unexpected query for GET {}: %s", sub_path, str(flask.request.args))
                flask.abort(400)
            if flask.request.args['service'] not in ['git-upload-pack', 'git-receive-pack']:
                app.logger.critical("Unexpected query for GET {}: %s", sub_path, str(flask.request.args))
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


    # TODO custom auth
    authenticated_user = flask.request.remote_user


    # logging details for now
    app.logger.info("handler: {} {} / {} / {}".format(flask.request.method, project_group, project, sub_path))
    app.logger.info("        :: {}".format(authenticated_user))
    if flask.request.args:
        app.logger.info("        :: {}".format(flask.request.args))
    app.logger.info("        : write {}".format(is_write))

    # determine and log permission for this request
    permission = Permissions(config, authenticated_user).get_permission(project_group, project)
    if permission['write'] and permission['read']:
        app.logger.info("User {} has permissions for read & write on: {}/{}".format(authenticated_user, project_group, project))
    elif permission['write']:
        app.logger.info("User {} has permissions for write on: {}/{}".format(authenticated_user, project_group, project))
    elif permission['read']:
        app.logger.info("User {} has permissions for read on: {}/{}".format(authenticated_user, project_group, project))
    if is_write and not permission['write']:
        app.logger.warning("User {} does not have write permission for: {}/{}".format(authenticated_user, project_group, project))
        flask.abort(403)
    elif not permission['read']:
        app.logger.warning("User {} does not have read permission for: {}/{}".format(authenticated_user, project_group, project))
        flask.abort(403)

    # run the cgi-bin with wrapper
    extra_env = {
        'GIT_PROJECT_ROOT': config['repo_root'],
        'GIT_HTTP_EXPORT_ALL': ''
    }
    # TODO if we identify the user set REMOTE_USER
    if flask.request.method == 'POST':
        return cgi_wrapper(config['bin_path'], extra_env, flask.request.data)   # TODO switch to flask.request.stream for input
    return cgi_wrapper(config['bin_path'], extra_env)





class Permissions(object):
    """Calculate permissions
    """
    def __init__(self, config, username):
        """Calculate permissions
        """
        self.config = config
        self.username = username
        self.user_authentication = None
        self.groups = None
        # resolve authentication
        if self.username not in config['authentication']:
            app.logger.warning("Username not found: {}".format(self.username))
            return
        self.user_authentication = config['authentication'][self.username]
        if 'groups' in self.user_authentication:
            self.groups = set(self.user_authentication['groups'])
        else:
            self.groups = set()

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
        authorisation = self.config['authorisation']
        # check project group
        if project_group not in authorisation:
            app.logger.info("Project Group no authorisation: {}".format(project_group))
            return permission
        authorisation = authorisation[project_group]
        if self._check_node(authorisation, permission):
            return permission
        # check project
        if project not in authorisation:
            app.logger.info("Project no authorisation: {}".format(project))
            return permission
        authorisation = authorisation[project]
        if self._check_node(authorisation, permission):
            return permission
        return permission
        


def load_config():
    """Load the config file specified in uwsgi environment GITGLUE_CONFIG

    :return: config contents (should be dict)
    """
    if 'GITGLUE_CONFIG' not in flask.request.environ:
        app.logger.critical("Configuration file not configured: GITGLUE_CONFIG must be in uwsgi environment")
        flask.abort(500)
    try:
        with open(flask.request.environ['GITGLUE_CONFIG'], 'rt') as f_conf:
            config = yaml.safe_load(f_conf)
    except FileNotFoundError:
        app.logger.critical("Configuration file not found: {}".format(flask.request.environ['GITGLUE_CONFIG']))
        flask.abort(500)
    except yaml.parser.ParserError as exc:
        app.logger.critical("Configuration file yaml error:\n{}".format(exc))
        flask.abort(500)
    # sanity check
    if 'authentication' not in config or not isinstance(config['authentication'], dict):
        app.logger.critical("Configuration file does not contain 'authentication' map")
        flask.abort(500)
    if 'authorisation' not in config or not isinstance(config['authorisation'], dict):
        app.logger.critical("Configuration file does not contain 'authorisation' map")
        flask.abort(500)
    return config


def cgi_wrapper(bin_path, extra_env=None, data=None):
    """Run cgi translating from flask environment

    :arg bin_path: str, binary to execute
    :arg data: str|None, optional data to pass to script (stdin) else will passh-through
    :return: flask response
    """
    # generate execution environment
    cgienv = {
        key: value
        for key, value in flask.request.environ.items()
        if not key.startswith(('uwsgi.', 'werkzeug.', 'wsgi.'))
    }
    cgienv['SERVER_SOFTWARE'] = 'cgiwrapper'
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
        if data is None:
            stdout, stderr = proc.communicate(flask.request.stream.read())
        else:
            stdout, stderr = proc.communicate(data)
    if proc.returncode != 0:
        app.logger.debug("{} returned {:d}".format(bin_path, proc.returncode))
        app.logger.debug("{} stdout:\n{}\n--- end stderr".format(bin_path, stdout))
        app.logger.debug("{} stderr:\n{}\n--- end stderr".format(bin_path, stderr))
        flask.abort(500)
    elif stderr:
        app.logger.debug("{} stderr:\n{}\n--- end stderr".format(bin_path, stderr))
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