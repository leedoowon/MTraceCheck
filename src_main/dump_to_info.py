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

## For input, see dump file example at the end of this script
## Output includes: number of unique 

def parseDumpInfo(numThreads, dumpFileName, outFileName):
    dumpFP = open(dumpFileName, "r")
    outFP = open(outFileName, "w")
    lastAddr = 0xC0 + 0x10 * (1 + numThreads)
    # e.g., numThreads=2 => lastAddr=0x400000F0
    searchMem = False
    # These data structure will be initialized everytime when new test run is found
    expIdx = None
    randIdx = None
    signatureSize = None
    lastSigAddr = None
    uniqueExec = None
    totalExec = None
    sortCycle = None
    cycleCounts = []
    eventCounts = []
    overflow = False
    for line in dumpFP:
        if (not searchMem):
            if (line.startswith("reading test_manager_")):
                # e.g.: "reading test_manager_0_0.bin"
                searchMem = True
                tokens = line.split("_")
                expIdx = tokens[2]
                randIdx = tokens[3].split(".")[0]
        else:
            if (line.startswith("40000")):
                offset = int(line[5:8], 16)
                if (offset == 0xC0):
                    tokens = line.split(" ")
                    signatureSize = int(tokens[1], 16)
                    lastSigAddr = int(tokens[2], 16)
                    uniqueExec = int(tokens[3], 16)
                    totalExec = int(tokens[4], 16)
                elif (offset == 0xD0):
                    tokens = line.split(" ")
                    sortCycle = int(tokens[1], 16)
                    if (not overflow and tokens[4] != "00000000"):
                        overflow = True
                elif (offset >= 0xE0 and offset <= lastAddr):
                    tokens = line.split(" ")
                    cycleCounts.append(int(tokens[1], 16))
                    eventCounts.append(int(tokens[3], 16))
                    if (not overflow and tokens[4] != "00000000"):
                        overflow = True
                if (offset == lastAddr):
                    searchMem = False
                    outFP.write("%s,%s,%s,%s,0x%X,%s,%s,%d,%s" %
                        (expIdx, randIdx, numThreads, signatureSize, lastSigAddr, uniqueExec, totalExec, overflow, sortCycle))
                    for cycleCount in cycleCounts:
                        outFP.write(",%s" % cycleCount)
                    for eventCount in eventCounts:
                        outFP.write(",%s" % eventCount)
                    outFP.write("\n")
                    expIdx = None
                    randIdx = None
                    signatureSize = None
                    lastSigAddr = None
                    uniqueExec = None
                    totalExec = None
                    sortCycle = None
                    cycleCounts = []
                    eventCounts = []
                    overflow = False
    dumpFP.close()
    outFP.close()

if __name__ == "__main__":
    if (len(sys.argv) != 4):
        print("Usage: python dump_to_info.py [number of threads] [captured dump log] [output csv file]")
        sys.exit(1)
    parseDumpInfo(int(sys.argv[1]), sys.argv[2], sys.argv[3])

"""
reading test_manager_0_0.bin
...
40000000: 02030000 00040000 02025c00 00000100    .........\......
40000010: 000002cf 00000200 02030000 00000000    ................
40000020: 00000000 00000000 00000000 00000000    ................
40000030: 00000000 00000000 00000000 00000000    ................
40000040: 00000000 00000000 00000000 00000000    ................
40000050: 00000000 00000000 00000000 00000000    ................
40000060: 00000000 00000000 00000000 00000000    ................
40000070: 00000000 00000000 00000000 00000000    ................
40000080: ffffffff ffffffff 7ffbfeff f7ffffdf    ................
40000090: 3bffff7f fffdd777 ffffffff ffffffff    ...;w...........
400000a0: fffffdff ffffffff fcfd57ef fff77fff    .........W......
400000b0: dc3f2fff ffffffff ffffffff ffffffff    ./?.............
400000c0: 00000002 a0000060 0000000c 00010000    ....`...........
400000d0: 0000f015 08000014 001cfa62 00000000    ........b.......
400000e0: 0011c3fb 08000014 00bee7b7 00000000    ................
400000f0: 0011c3f7 08000014 00c75605 00000000    .........V......
40000100: 00000000 00000000 00000000 00000000    ................
40000110: 00000000 00000000 00000000 00000000    ................
40000120: 00000000 00000011 00000000 00000000    ................
40000130: 00000000 00000000 00010000 00200000    .............. .
40000140: 00000000 00000000 00000000 00000000    ................
40000150: 00000000 00000000 00000000 00000000    ................
40000160: 00000000 00000000 00000000 00000000    ................
40000170: 00000000 00000000 00000000 00000000    ................
"""
