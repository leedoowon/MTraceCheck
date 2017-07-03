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

############################################################
## Parse the history log file
############################################################

""" Format
### Execution 0
T0: 0-FFFF001E,D,FFFF000D 1-10006 2-FFFF000B,FFFF0009,0 3-10006,38,52 4-3B 5-A,0,FFFF0004,52 6-FFFF0005,19 7-52,0 8-6,24,29,C,29 9-FFFF0019 10-F,10036 11-10036,29 12- 13-20,10010,10043 14-FFFF0005,10024,19,10010,10045,10043 15-1D,29,5F
T1: 0-FFFF0017,3,19,1E,10006,10051,29 1-1,A,10012,1E,10006,10050 2-10010,C 3-FFFF000D,10024,20,10006,FFFF000D 4-FFFF001A,10050 5-9,1001D,14,1002D 6-10017,38 7-FFFF0003,FFFF0007,24,FFFF000D,38,53,1002D 8-10005,10057 9-FFFF0003,9,2B,29,10036 10-FFFF001D 11-FFFF0008,10010,F,10010,0,2B,10036,10006 12-FFFF0002,FFFF000D,10033 13-FFFF001E,1001C,C 14-24,10045 15-14,20,3B
### Execution 1
T0: 0-FFFF001E,D,FFFF000D 1-10006 2-FFFF000B,10010,0 3-10006,38,52 4-3B 5-A,0,FFFF0004,52 6-FFFF0005,19 7-52,0 8-6,24,29,C,29 9-FFFF0019 10-F,10036 11-10036,29 12- 13-20,10010,1003C 14-FFFF0005,13,19,10010,10045,10043 15-1D,29,5F
T1: 0-FFFF0017,29,19,3A,10006,10051,29 1-1,A,10012,1E,10006,10050 2-10010,C 3-FFFF000D,2B,20,10006,46 4-FFFF001A,10050 5-9,1001D,14,1002D 6-20,38 7-FFFF0003,FFFF0007,24,FFFF000D,38,53,1002D 8-10005,10057 9-FFFF0003,9,2B,29,10036 10-FFFF001D 11-FFFF0008,10010,F,10010,0,2B,10036,10006 12-FFFF0002,FFFF000D,10033 13-19,1001C,C 14-24,10045 15-14,20,4C
...
"""

# hist[executionIndex][threadIndex][registerIndex] = history of loaded value to the register

def parseHistoryFile(filenames, verbosity):
    hist = dict()
    for histFileName in filenames:
        histFP = open(histFileName, "r")
        if (verbosity > 0):
            print("Processing %s" % (histFileName))
        executionIndex = None
        threadIndex = None

        for line in histFP:
            if (line.startswith("### Execution ")):  # 14 characters
                executionIndex = int(line[14:])
                assert(executionIndex not in hist)
                hist[executionIndex] = dict()
            else:
                assert(executionIndex != None)
                assert(line.startswith("T"))
                tempIndex = line.find(":")
                threadIndex = int(line[1:tempIndex])
                assert(threadIndex not in hist[executionIndex])
                hist[executionIndex][threadIndex] = dict()

                line = line[tempIndex+1:]
                registerTokens = line.split()
                for registerToken in registerTokens:
                    tokens = registerToken.split("-")
                    registerIndex = int(tokens[0])
                    assert(registerIndex not in hist[executionIndex][threadIndex])
                    loadValueTokens = tokens[1].split(",")
                    if (len(loadValueTokens) == 1 and loadValueTokens[0] == ""):  # no load value
                        continue
                    #print(loadValueTokens)
                    loadValues = []
                    for loadValueToken in loadValueTokens:
                        loadValues.append(int(loadValueToken, 16))
                    hist[executionIndex][threadIndex][registerIndex] = loadValues
        histFP.close()
    return hist

