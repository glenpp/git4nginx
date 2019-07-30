#!/bin/sh
# create all hook links back to master script
# run in repo (or hooks/)
#
# git-glue tools for using git via http(s) with Nginx
# Copyright (C) 2019  Glen Pitt-Pladdy
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#


HOOKS="
	applypatch-msg
	commit-msg
	fsmonitor-watchman
	p4-pre-submit
	post-checkout
	post-commit
	post-merge
	post-receive
	post-rewrite
	post-update
	pre-applypatch
	pre-auto-gc
	pre-commit
	prepare-commit-msg
	pre-push
	pre-rebase
	pre-receive
	push-to-checkout
	sendemail-validate
	update
"

MASTER_DIR=`dirname "$0"`
MASTER_DIR=`realpath "$MASTER_DIR"`
MASTER_HOOK="$MASTER_DIR/master_hook.py"
if [ ! -x "$MASTER_HOOK" ]; then
	echo "Master hook is not where we expect: $MASTER_HOOK" >&2
	echo "Is this script in the same location?" >&2
	exit 1
fi

# get into repo hooks directory
if pwd | grep '\.git/hooks$'; then
	echo "in hooks/"
elif pwd | grep '\.git$' && [ -d hooks ]; then
	echo "in repo, changing to hooks/"
	cd hooks/
else
	echo "Run this in the repo (ends .git/) or in the hooks dir (ens .git/hooks/)" >&2
	exit 1
fi

# create links
for hook in $HOOKS
do
	echo "Linking $hook..."
	ln -s "$MASTER_HOOK" "$hook"
done
echo "done"

