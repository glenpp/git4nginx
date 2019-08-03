#!/bin/sh
# Create a suitable repo with protections

usage() {
	echo "Create a new repo below the current directory" >&2
	echo "Usage: $0 [repo name]" >&2
	echo "  If no repo name is provided then prompted" >&2
	echo "  The .git will be automatically appended" >&2
	echo "  Ensure the name does not contain spaces or special characters." >&2
	exit 1
}

if [ $# -eq 1 ]; then
	repo_name=$1
else
	read -p "Enter repo name: " repo_name
fi
# sanity checks
echo "$repo_name" | grep --perl-regexp '^[\w\-]{3,64}$' || usage
repo_dir="$repo_name.git"
if [ -d "$repo_dir" ]; then
	echo "$repo_dir exists already" >&2
	usage
fi

# create
git init --bare "$repo_dir"

# customisation...
cd "$repo_dir"

# see https://www.git-scm.com/book/en/v2/Customizing-Git-Git-Configuration
echo "Protect against rewriting"
# stop force-pushes
git config --local receive.denyNonFastforwards true
# stop working around the above
git config --local receive.denyDeletes true

