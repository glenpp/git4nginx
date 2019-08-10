"""Only lookup groups, authentication occured upstream (ie. with Nginx)

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


def authenticate(logger, auth_config, username, password):
    """Sanity check and lookup the groups and other info

    Authentication should hav ehappened upstream, hence password should always be None.

    :arg logger:
    :arg auth_config: dict, authentication config for plugin
    :arg username: str, username client is authenticating with
    :arg password: str|None, password client is authanticating with
        IMPORTANT: this should always be None for this plugin which requires
        upstream authentication so password will not be decoded from headers.
    :return: tuple of:
        authenticated: bool, if the user is successfully authenticated
        groups: list, groups user has membership of
        info: dict, additional info exposed to hooks
    """
    # sanity check
    if password is not None:
        logger.critical("Authentication plugin requires upstream authentication to be configured")
        return False, [], {}
    # check user exists in config
    users = auth_config['users']
    if username not in users:
        logger.warning("Username not found in configured users: %s", username)
        return False, [], {}
    # lookup groups
    groups = []
    if 'groups' in users[username]:
        groups = users[username]['groups']
    # lookup info
    info = {}
    if 'info' in users[username]:
        info = users[username]['info']
    # done
    return True, groups, info
