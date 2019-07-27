#!/bin/sh
# run from repo (or hooks/) to create all hook links back to master script

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

