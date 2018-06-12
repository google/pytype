#! /usr/bin/python -B
"""Copy a group of files from a source directory to a destination directory.

Usage:
  copy.py -s <SOURCE_DIRECTORY> -d <DESTINATION_DIRECTORY> file1 [file2 ...]
"""

import argparse
import os
import shutil
import sys


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-s", "--src_dir", type=str, required=True,
                      help="The source directory.")
  parser.add_argument("-d", "--dst_dir", type=str, required=True,
                      help="The destination directory.")
  parser.add_argument("file_list", metavar="FILE", type=str, nargs="+",
                      help="List of files to copy.")
  args = parser.parse_args()
  return args


def copy_file(src_dir, dst_dir, filename):
  dst_file = os.path.join(dst_dir, filename)
  dst_parent = os.path.dirname(dst_file)
  if not os.path.exists(dst_parent):
    # Create the intermediate directories if they do not exist
    os.makedirs(dst_parent)
  shutil.copy(os.path.join(src_dir, filename), dst_file)


def main():
  args = parse_args()
  if not os.path.exists(args.src_dir):
    sys.exit("Source directory '%s' does not exist." % args.src_dir)
  if not os.path.exists(args.dst_dir):
    sys.exit("Destination directory '%s' does not exist" % args.dst_dir)
  for filename in args.file_list:
    copy_file(args.src_dir, args.dst_dir, filename)


if __name__ == "__main__":
  main()
