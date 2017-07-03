#!/usr/bin/python

##########################################################################
#
# MTraceCheck
# Copyright 2017 The Regents of the University of Michigan
# Doowon Lee and Valeria Bertacco
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
##########################################################################

import os
import sys
import argparse

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("inputs", metavar="files", nargs="+", help="files to be diffed")
args = parser.parse_args()

verbosity = args.verbose

#inputFileListString = " ".join(str(x) for x in args.inputs)
#if (verbosity > 0):
#    print("Files: %s" % inputFileListString)
#os.system("md5sum %s | cut --bytes=-32 > md5_all.txt" % (inputFileListString))

# 2016/8/8. Routine changed due to the first line in hist*.txt files
# (1st line include "### Execution...")

os.system("rm -f md5_all.txt")
# Filter out lines starting with #
for inputFile in args.inputs:
    cmdString = "sed \'/^#/d\' %s | md5sum | cut --bytes=-32 >> md5_all.txt" % inputFile
    os.system(cmdString)
    
os.system("sort md5_all.txt | uniq --count > md5_uniq.txt")
