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

def main(argv=sys.argv[1:]):
	args = argparser.parse_args(argv)

	if args.command == "add":
		git_add(args)
	elif args.command == "cat-file":
		git_cat_file(args)
	elif args.command == "checkout":
		git_checkout(args)
	elif args.command == "commit":
		git_commit(args)
	elif args.command == "hash-object":
		git_hash_object(args)
	elif args.command == "init":
		git_init(args)
	elif args.command == "log":
		git_log(args)
	elif args.command == "ls-tree":
		git_ls_tree(args)
	elif args.command == "merge":
		git_merge(args)
	elif args.command == "rebase":
		git_rebase(args)
	elif args.command == "rev-parse":
		git_rev_parse(args)
	elif args.command == "rm":
		git_rm(args)
	elif args.command == "show-ref":
		git_show_ref()
	elif args.command == "tag":
		git_tag()
	else:
		print("no")
