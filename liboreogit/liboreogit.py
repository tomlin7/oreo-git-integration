import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib


argparser = argparse.ArgumentParser(description="This stupid content parser")

argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")

argsp.add_argument("path",
	metavar="directory",
	nargs="?",
	default=".",
	help="Where to create the repository.")


class GitRepository(object):
    """
    A git repository
    """

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")

def repo_path(repo, *path):
	"""
	Compute path under repo's gitdir
	"""
	return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
	"""
	Same as repo_path, but create dirname(*path) if absent.
	For example, repo_file(r, 'refs', 'remotes', 'origin', 'HEAD')
	will create .git/refs/remotes/origin.
	"""

	if repo_dir(rep, *path[:-1], mkdir=mkdir):
		return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
	"""
	Same as repo_path, but mkdir *path if absent
	"""

	path = repo_path(repo, *path)

	if os.path.exists(path):
		if (os.path.isdir(path)):
			return True
		else:
			raise Exception(f"Not a directory {path}")

	if mkdir:
		os.makedirs(path)
		return repo_path
	else:
		return 0


def repo_create(path):
	"""Create a new repository at path"""

	repo = GitRepository(path, True)

	# check: path either doesn't exist or is empty
	if os.path.exists(repo.worktree):
		if not os.path.isdir(repo.worktree):
			raise Exception(f"{path} is not a directory!")
		if os.listdir(repo.worktree):
			raise Exception(f"{path} is not empty!")
	else:
		os.makedirs(repo.worktree)

	assert(repo_dir(repo, "branches", mkdir=True))
	assert(repo_dir(repo, "objects", mkdir=True))
	assert(repo_dir(repo, "refs", "tags", mkdir=True))
	assert(repo_dir(repo, "refs", "heads", mkdir=True))

	# .git/description
	with open(repo_file(repo, "description"), "w") as f:
		f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

	# .git/HEAD
	with open(repo_file(repo, "HEAD"), "w") as f:
		f.write("ref: refs/heads/master\n")

	with open(repo_file(repo, "config"), "w") as f:
		config = repo_default_config()
		config.write(f)

	return repo


def repo_default_config():
	ret = configparser.ConfigParser()

	ret.add_section("core")
	ret.set("core", "repositoryformatversion", "0")
	ret.set("core", "filemode", "false")
	ret.set("core", "bare", "false")

	return ret

def repo_find(path=".", required=True):
	path = os.path.realpath(path)

	if os.path.isdir(os.path.join(path, ".git")):
		return GitRepository(path)

	# haven't returned, recurse in parent
	parent = os.path.realpath(os.path.join(path, ".."))

	if parent == path:
		# Bottom case
		# os.path.join("/", "..") == "/""
		# If parent==path, then path is root.
		if required:
			raise Exception("No git directory.")
		else:
			return None

	# Recursive case
	return repo_find(parent, required)


class GitObject(object):
	repo = None

	def __init__(self, repo, data=None):
		self.repo = repo

		if data != None:
			self.deserialze(data)

	def serialize(self):
		"""
		MUST be implemented by subclasses.
		"""
		raise Exception("Unimplemented!")

	def deserialze(self, data):
		raise Exception("Unimplemented!")

def object_read(repo, sha):
	"""
	Read object's object_id from Git repository. 
	Return a GitObject whose exact type depends on the object
	"""

	path = repo_file(repo, "objects", sha[0:2], sha[2:])

	with open(path, "rb") as f:
		raw = zlib.decompress(f.read())

		# Read object type
		x = raw.find(b' ')
		fmt = raw[0:x]

		# Read and validate object size
		y = raw.find(b'\x00', x)
		size = int(raw[x:y].decode("ascii"))
		if size != len(raw) - y - 1:
			raise Exception(f"Malformed object {sha}: bad length")

		# Pick constructor
		if fmt == b'commit':
			c = GitCommit
		elif fmt == b'tree':
			c = GitTree
		elif fmt == b'tag':
			c = GitTag
		elif fmt == b'blob':
			c = GitBlob
		else:
			raise Exception("Unknown type {0} for object {1}".format(fmt.decode("ascii"), sha))

		# Call constructor and return object
		return c(repo, raw[y+1:])

def object_find(repo, name, fmt=None, follow=True):
	return name


def cmd_init(args):
	repo_create(args.path)


def main(argv=sys.argv[1:]):
	args = argparser.parse_args(argv)

	if args.command == "add":
		cmd_add(args)
	elif args.command == "cat-file":
		cmd_cat_file(args)
	elif args.command == "checkout":
		cmd_checkout(args)
	elif args.command == "commit":
		cmd_commit(args)
	elif args.command == "hash-object":
		cmd_hash_object(args)
	elif args.command == "init":
		cmd_init(args)
	elif args.command == "log":
		cmd_log(args)
	elif args.command == "ls-tree":
		cmd_ls_tree(args)
	elif args.command == "merge":
		cmd_merge(args)
	elif args.command == "rebase":
		cmd_rebase(args)
	elif args.command == "rev-parse":
		cmd_rev_parse(args)
	elif args.command == "rm":
		cmd_rm(args)
	elif args.command == "show-ref":
		cmd_show_ref()
	elif args.command == "tag":
		cmd_tag()
	else:
		print("no")
