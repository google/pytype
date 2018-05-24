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


def main():
  args = parse_args()
  src_dir = args.src_dir
  dst_dir = args.dst_dir
  if not os.path.exists(src_dir):
    sys.exit("Source directory '%s' does not exist." % src_dir)
  if not os.path.exists(dst_dir):
    sys.exit("Destination directory '%s' does not exist" % dst_dir)

  def check_file_exists(filename):
    if not os.path.exists(filename):
      sys.exit("Source file '%s' does not exist" % filename)
  src_file_list = [os.path.join(src_dir, f) for f in args.file_list]
  map(check_file_exists, src_file_list)

  def copy_file(filename):
    dst_file = os.path.join(dst_dir, filename)
    dst_parent = os.path.dirname(dst_file)
    if not os.path.exists(dst_parent):
      # Create the intermediate directories if they do not exist
      os.makedirs(dst_parent)
    shutil.copy(os.path.join(src_dir, filename),
                os.path.join(dst_dir, filename))
  map(copy_file, args.file_list)


if __name__ == "__main__":
  main()
