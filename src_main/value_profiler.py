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
import instruction
import parse_prog

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--output", "-o", default="test.txt")
parser.add_argument("--no-profile", action="store_true", default=False)
parser.add_argument("input", metavar="program file", help="program description file to be processed")
args = parser.parse_args()

verbosity = args.verbose

def createAsmCode(loadRegisterIndex, valueTargets):
    asmString = "profile r%d,[" % loadRegisterIndex
    firstTarget = True
    for target in valueTargets:
        targetThread = instruction.getThreadIndex(target)
        targetInst = instruction.getInstIndex(target)
        if (firstTarget):
            asmString += "0x%X" % (target)
        else:
            asmString += "/0x%X" % (target)
        firstTarget = False
    asmString += "]"
    return asmString

def generateIntermediateProg(orgProg, profileEnable, storeTable, verbosity):
    outProg = dict()
    for thread in orgProg:
        outProg[thread] = []
        sortedInstList = sorted(orgProg[thread].keys())
        if (verbosity > 0):
            print("Thread %d: %s" % (thread, sortedInstList))
        for sortedInst in sortedInstList:
            asm = orgProg[thread][sortedInst]
            # 1. Write original asm code
            if (instruction.getInstType(asm) == 1):  # store
                # append store identifier
                outProg[thread].append(asm + ",0x%X" % instruction.getMemOp(thread, sortedInst))
            else:
                outProg[thread].append(asm)
            # 2. Write instrumented asm code
            if (profileEnable and instruction.getInstType(asm) == 0):
                # See parse_prog.py for assembly code examples
                tokens = asm.split(",")
                assert(len(tokens) > 1)
                registerString = tokens[1]
                assert(registerString[0] == "r")
                registerIndex = int(registerString[1:])
                addressString = tokens[0].split(" ")[1]
                addressInt = int(addressString, 16)
                valueTargets = [instruction.getMemOp(0xffff, addressInt)]  # initial memory value
                #
                # TODO: Smarter store-target filtering
                #       Some targets are invalid and can be decided statically
                #
                if addressInt in storeTable:
                    mostRecentIntraIndex = None
                    for storeTarget in storeTable[addressInt]:
                        if (instruction.getThreadIndex(storeTarget) != thread):
                            # Inter-thread candidate stores
                            valueTargets.append(storeTarget)
                        else:
                            # NOTE: Assume that store indices are sorted in ascending order
                            storeIntraIndex = instruction.getInstIndex(storeTarget)
                            if (storeIntraIndex < sortedInst):
                                mostRecentIntraIndex = storeIntraIndex
                    if (mostRecentIntraIndex != None):
                        valueTargets.append(instruction.getMemOp(thread, mostRecentIntraIndex))
                profileAsm = createAsmCode(registerIndex, valueTargets)
                #print(profileAsm)
                outProg[thread].append(profileAsm)
    return outProg

def generateIntermediateFile(orgProg, profileEnable, storeTable, outFileName, verbosity):
    outProg = generateIntermediateProg(orgProg, profileEnable, storeTable, verbosity)
    outFilePtr = open(outFileName, "w")
    # 1. Write header (test configuration)
    # TODO: Fill this header if necessary
    outFilePtr.write("### Test configuration\n")
    # 2. Write test code
    for thread in outProg:
        outFilePtr.write("### Thread %d\n" % thread)
        for asm in outProg[thread]:
            outFilePtr.write("%s\n" % asm)
    outFilePtr.close()
    if (verbosity > 0):
        print("Test description %s created" % outFileName)

if __name__ == "__main__":
    returnDict = parse_prog.parseProgram(args.input, None, False, verbosity)
    orgProg = returnDict["progInfo"]
    storeTable = returnDict["storeTable"]
    generateIntermediateFile(orgProg, not args.no_profile, storeTable, args.output, verbosity)
