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

import sys

class ExecutionState:
    IDLE = 0
    WAIT = 1
    READY = 2
    PERFORMED = 3


class Instruction:

    # doowon, 2017/09/06, fences

    ## Class variables
    # instType: -1 (uninitialized), 0 (load), 1 (store), 2 (fence)
    # address: -1 (uninitialized), 0 -- (numMemLocs-1)
    # loadTarget: -1 (uninitialized), 0 -- (numHistRegs-1)
    # value: value that is read in load op
    #        (ignore this value in store op)

    def __init__(self, paramType=-1, paramAddress=-1, paramLoadTarget=-1):
        self.instType = paramType
        self.address = paramAddress
        self.loadTarget = paramLoadTarget
        self.value = 0xffffffff
        self.intraDeps = []
        self.interDeps = []
        self.exeState = ExecutionState.IDLE
        self.sortEdges = set()  # Set removes redundancy
        self.sortReverseEdges = set()
        self.sortOrder = None

    def genInst(self, paramType, paramAddress, paramLoadTarget):
        self.instType = paramType
        self.address = paramAddress
        self.loadTarget = paramLoadTarget

    def writeValue(self, paramValue):
        self.value = paramValue

    def addIntraDep(self, memOp):
        self.intraDeps.append(memOp)

    def addInterDep(self, memOp):
        self.interDeps.append(memOp)

    def addSortEdge(self, memOp):
        self.sortEdges.add(memOp)

    def removeSortEdge(self, memOp):
        self.sortEdges.remove(memOp)

    def addReverseEdge(self, memOp):
        self.sortReverseEdges.add(memOp)
        # No need to remove elements once they are added

    def setState(self, paramExeState):
        self.exeState = paramExeState

    def resetInst(self):
        self.exeState = ExecutionState.IDLE
        self.value = 0xffffffff
        del self.interDeps[:]
        self.sortEdges.clear()
        self.sortReverseEdges.clear()
        self.sortOrder = None

    def printInst(self):
        sys.stdout.write("Instruction: ")
        if (self.instType == 0):
            sys.stdout.write("ld ")
            sys.stdout.write("0x%x" % (self.address))
            sys.stdout.write(",r%d" % (self.loadTarget))
            sys.stdout.write(",0x%x\n" % (self.value))
        elif (self.instType == 1):
            sys.stdout.write("st ")
            sys.stdout.write("0x%x\n" % (self.address))
        elif (self.instType == 2):
            sys.stdout.write("fence")
            # TODO: Fine-grained fences
        else:
            print ("Error: Unrecognized instruction type %d" % self.instType)
            sys.exit(1)

    def getAssembly(self):
        # NOTE: Whenever you change this assembly format, change functions
        #       to parse assembly code defined below
        string = ""
        if (self.instType == 0):
            string += "ld "
            string += "0x%x" % (self.address)
            string += ",r%d" % (self.loadTarget)
        elif (self.instType == 1):
            string += "st "
            string += "0x%x" % (self.address)
        elif (self.instType == 2):
            string += "fence"
        else:
            print ("Error: Unrecognized instruction type %d" % self.instType)
            sys.exit(1)
        return string

def getThreadIndex(memOp):
    return ((memOp >> 16) & 0xffff)

def getInstIndex(memOp):
    return (memOp & 0xffff)

def getMemOp(threadIndex, instIndex):
    return (((threadIndex & 0xffff) << 16) | (instIndex & 0xffff))

def getMemId(threadIndex, instIndex):
    return "m%d_%d" % (threadIndex, instIndex)

# Assembly parsing
def getInstType(asm):
    tokens = asm.split(" ")
    if (tokens[0] == "ld"):
        return 0
    elif (tokens[0] == "st"):
        return 1
    elif (tokens[0] == "fence"):
        return 2
    else:
        print("Error: unsupported instruction type when parsing assembly code %s" % asm)
        sys.exit(1)

def getAddress(asm):
    tokens = asm.split(" ")
    instType = getInstType(asm)
    if (instType == 0):  # load
        lastIdx = tokens[1].find(",")
        assert(lastIdx != -1)
        return int(tokens[1][:lastIdx], 16)
    elif (instType == 1): # store
        return int(tokens[1], 16)
    else:
        # not reachable
        sys.exit(1)

