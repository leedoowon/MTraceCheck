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

def parseIntermediate(intermediate_file, verbosity):
    intermediateFP = open(intermediate_file, "r")
    intermediate = dict()
    header = dict()

    # See exp/160812_codegen_x86/test.txt for an example of intermediate program file
    headerDetected = False  # True if parser meets the start of header
    headerDone = False      # True if parser meets the end of header
    currThread = None
    for line in intermediateFP:
        if (line.startswith("### ")):
            # SECTION delimiter
            if (line[4:] == "Test configuration"): # e.g.: "### Test configuration"
                headerDetected = True
            elif (line[4:].startswith("Thread")):  # e.g.: "### Thread 0"
                if (not headerDone):
                    headerDone = True
                currThread = int(line[10:])
        elif (headerDetected and not headerDone):
            # HEADER section
            tokens = line.split(" ")  # e.g., "numThread 2"
            assert(len(tokens) == 2)
            try:
                value = int(tokens[1])
            except:
                value = tokens[1]
            header[tokens[0]] = value
        else:
            # THREAD section
            assert(currThread != None)
            if (not currThread in intermediate):
                intermediate[currThread] = []
            if (line.startswith("ld")):
                # e.g.: "ld 0x19,r9"
                tokens = line[3:].split(",")
                address = int(tokens[0], 16)
                registerIndex = int(tokens[1][1:], 10) # after removing integer after "r"
                intermediate[currThread].append({"type": "ld", "addr": address, "reg": registerIndex})
            elif (line.startswith("st")):
                # e.g.: "st 0x1b,0x0"  (0x1b: address, 0x0: value)
                tokens = line[3:].split(",")
                address = int(tokens[0], 16)
                value = int(tokens[1], 16)
                intermediate[currThread].append({"type": "st", "addr": address, "value": value})
            # doowon, 2017/09/06, fences added
            elif (line.startswith("fence")):
                intermediate[currThread].append({"type": "fence"})
            elif (line.startswith("profile")):
                # e.g.: "profile r8,[0xFFFF000A/0x6/0x12/0x15/0x1000C/0x1002D]"
                tokens = line[8:].split(",")
                registerIndex = int(tokens[0][1:], 10)
                targetList = tokens[1][tokens[1].find("[")+1 : tokens[1].find("]")]  # after removing '[' and ']'
                targetHexs = targetList.split("/")
                targets = []
                for targetHex in targetHexs:
                    targets.append(int(targetHex, 16))
                intermediate[currThread].append({"type": "profile", "reg": registerIndex, "targets": targets})
            else:
                print("Error: Unrecognized intermediate code %s" % line)
                sys.exit(1)

    intermediateFP.close()

    return {"header": header, "intermediate": intermediate}
