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

argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects.")
argsp.add_argument("type",
	metavar="type",
	choices=["blob", "commit", "tag", "tree"],
	help="Specify the type")
argsp.add_argument("object",
	metavar="object",
	help="The object to display")

argsp = argsubparsers.add_parser(
	"hash-object",
	help="Compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t",
	metavar="type",
	dest="type",
	choices=["blob", "commit", "tag", "tree"],
	default="blob",
	help="Specify a type")
argsp.add_argument("-w",
	dest="write",
	action="store_true",
	help="Actually write the object into database")
argsp.add_argument("path",
	help="Read object from <file>")

argsp = argsubparsers.add_parser(
	"log", help="Display history of a given commit.")
argsp.add_argument("commit",
	default="HEAD",
	nargs="?",
	help="Commit to start at.")



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

def cmd_init(args):
	repo_create(args.path)

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

def object_write(obj, actually_write=True):
	# Serialize object data
	data = obj.serialize()
	# Add header
	result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
	# Compute hash
	sha = hashlib.sha1(result).hexdigest()

	if actually_write:
		# Compute path
		path = repo_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir=actually_write)

		with open(path, 'wb') as f:
			# Compress and write
			f.write(zlib.compress(result))

	return sha

class GitBlob(GitObject):
	fmt = b'blob'

	def serialize(self):
		return self.blobdata

	def deserialze(self, data):
		self.blobdata = data

def cmd_cat_file(args):
	repo = repo_find()
	cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
	obj = object_read(repo, object_find(repo, obj, fmt=fmt))
	sys.stdout.buffer.write(obj.serialize())

def cmd_hash_object(args):
	if args.write:
		repo = GitRepository(".")
	else:
		repo = None

	with open(args.path, "rb") as fd:
		sha = objec_hash(fd, args.type.encode(), repo)
		print(sha)

def object_hash(fd, fmt, repo=None):
	data = fd.read()

	# Choose constructor depending on 
	# object type found in header
	if fmt == b'commit':
		obj = GitCommit(repo, data)
	elif fmt == b'tree':
		obj = GitTree(repo, data)
	elif fmt == b'tag':
		obj = GitTag(repo, data)
	elif fmt == b'blob':
		obj = GitBlob(repo, data)
	else:
		raise Exception(f"Unknown type {fmt}")

	return object_write(obj, repo)

# Short for "Key-Value List with Message"
def kvlm_parse(raw, start=0, dct=None):
	if not dct:
		dct = collections.OrderedDict()
		# declaring the argument as dct=OrderedDict() will make all
		# functions calls endlessly grow the same dict.

	# search for the next space and the next newline
	spc = raw.find(b' ', start)
	nl = raw.find(b'\n', start)

	# If space appears before newline, we have a keyword

	# Base Case
	# =========
	# If newline appears first (or there's no space at all, in which
	# case find returns -1), we assume a blank line. A blank line
	# means the remainder of the data is the message.
	if (spc < 0) or (nl < spc):
		assert(nl == start)
		dct[b''] = raw[start+1:]
		return dct

	# Recursive Case
	# ==============
	# read a key-value pair and recurse for the next.
	key = raw[start:spc]

	# Find the end of the value. Continuation lines begin with a
	# space, so we loop until finds a "\n" not followed by a space.
	end = start
	while True:
		end = raw.find(b'\n', end+1)
		if raw[end+1] != ord(' '): break

	# Grab the value
	# Also, drop the leading space on continuation lines
	value = raw[spc+1:end].replace(b'\n ', b'\n')

	# Don't overwrite existing data contents
	if key in dct:
		if type(dct[key]) == list:
			dct[key].append(value)
		else:
			dct[key] = [dct[key], value]
	else:
		dct[key] = value

	return kvlm_parse(raw, start=end+1, dct=dct)

def kvlm_serialize(kvlm):
	ret = b''

	# Output fields
	for k in kvlm.keys():
		# Skip the message itself
		if k == b'': continue
		val = kvlm[k]
		# Normalize to a list
		if type(val) != list:
			val = [val]

		for v in val:
			ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'

	# Append message
	ret += b'\n' + kvlm[b'']

	return ret

class GitCommit(GitObject):
	fmt = b'commit'

	def deserialze(self, data):
		self.kvlm = kvlm_parse(data)

	def serialize(self):
		return kvlm_serialize(self.kvlm)

def cmd_log(args):
    repo = repo_find()

    print("digraph wyaglog{")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    
    seen.add(sha)

    commit = object_read(repo, sha)
    assert(commit.fmt == b'commit')

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return

    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [parents]

    for p in parents:
        p = p.decode("ascii")
        print("c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)

class GitTreeLeaf(object):
	def __init__(self, mode, path, sha):
		self.mode = mode
		self.path = path
		self.sha = sha

def tree_parse_one(raw, start=0):
	# Find the space terminator of the mode
	x = raw.find(b' ', start)
	assert(x - start == 5 or x - start == 9)

	# Read the mode
	mode = raw[start:x]

	# Find the NULL terminator of the path and read the path
	y = raw.find(b'\x00', x)
	path = raw[x+1:y]

	# Read the SHA and convert to an hex string
	sha = hex(
		int.from_bytes(
			raw[y+1:y+21], "big"))[2:] # hex() adds 0x in front

	return y + 21, GitTreeLeaf(mode, path, sha)

def tree_parse(raw):
	pos = 0
	max = len(raw)
	ret = list()
	while pos < max:
		pos, data = tree_parse_one(raw, pos)
		ret.append(data)

	return ret

def tree_serialize(obj):
	ret = b''
	for i in obj.items:
		ret += i.mode
		ret += b' '
		ret += i.path
		ret += b'\x00'
		sha = int(i.sha, 16)
		ret += sha.to_bytes(20, byteorder="big")

class GitTree(GitObject):
	fmt = b'tree'

	def deserialze(self, data):
		self.items = tree_parse(data)

	def serialize(self):
		return tree_serialize(self)

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
