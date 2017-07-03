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
import parse_hist
import copy

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--ignore-reg", action="store_true", default=False)
parser.add_argument("--program-file", "-p", help="intermediate file that describes test program and intra-thread dependency", default="prog.txt")
parser.add_argument("--wo-file", help="intermediate write-order file name", default="wo.txt")
parser.add_argument("--single-copy-atomicity", action="store_true", default=False)
parser.add_argument("inputs", metavar="history files", nargs="+", help="history files to be processed")
args = parser.parse_args()

verbosity = args.verbose

############################################################
## Set dependency propagation
############################################################

# TODO: algorithmic improvement
def setDependencyPropagation(depSet):
    # Convert the set into a flat set
    flatSet = dict() # a dict which uses thread+inst as index
    for thread in depSet:
        for inst in depSet[thread]:
            memIndex = instruction.getMemOp(thread, inst)
            flatSet[memIndex] = set(depSet[thread][inst])

    numInsts = len(flatSet)
    visited = dict()
    for memIndex in flatSet:
        visited[memIndex] = False
    visitedCount = 0
    readyList = []
    while True:
        #print("readyList %s" % readyList)
        if (len(readyList) == 0):
            # Add instructions with no unvisited dependent instructions
            for memIndex in flatSet:
                if (not visited[memIndex]):
                    ready = True
                    for depMemIndex in flatSet[memIndex]:
                        if not visited[depMemIndex]:
                            ready = False
                            break
                    if ready:
                        readyList.append(memIndex)
            # Check if there is no added instruction
            if (len(readyList) == 0):
                if (visitedCount == numInsts):
                    # All instructions in the thread are propagated
                    break
                else:
                    # There is unvisited instruction(s)
                    print("Error: Cyclic dependency")
                    print("numInsts %d visitedCount %d" % (numInsts, visitedCount))
                    print("visited %s" % visited)
                    for memIndex in flatSet:
                        if (not visited[memIndex]):
                            sys.stdout.write("%X:" % memIndex)
                            for depMemIndex in flatSet[memIndex]:
                                #sys.stdout.write(" %X" % depMemIndex)
                                if (not visited[depMemIndex]):
                                    sys.stdout.write(" %X" % depMemIndex)
                            sys.stdout.write("\n")
                    sys.exit(1)
        else:
            visitMemIndex = readyList.pop(0)
            visited[visitMemIndex] = True
            visitedCount += 1
            #print("picked visitMemIndex %X" % visitMemIndex)
            #print("dependency %s" % flatSet[visitMemIndex])
            addedSet = set()
            for depMemIndex in flatSet[visitMemIndex]:
                addedSet |= flatSet[depMemIndex]
            flatSet[visitMemIndex] |= addedSet

    # Convert back the flat set to the original hierarchical data structure
    for memIndex in flatSet:
        thread = instruction.getThreadIndex(memIndex)
        inst = instruction.getInstIndex(memIndex)
        depSet[thread][inst] = flatSet[memIndex]

    return depSet

############################################################
## Parse program
############################################################

if (verbosity > 0):
    print("INFO: Reading a testcase description %s" % (args.program_file))

returnDict = parse_prog.parseProgram(args.program_file, args.wo_file, args.ignore_reg, verbosity)
prog = returnDict["progInfo"]
intra = returnDict["intraDep"]
writeOrder = returnDict["writeOrder"]
lookupInstFromLoad = returnDict["lookupTable"]

#print("DEBUG: writeOrder %s" % writeOrder)

############################################################
## Parse history log file
############################################################

hist = parse_hist.parseHistoryFile(args.inputs, verbosity)

# debug
if (verbosity > 1):
    for executionIndex in hist:
        for thread in hist[executionIndex]:
            sys.stdout.write("Execution %d T%d" % (executionIndex, thread))
            sys.stdout.write("\n")
            for registerIndex in hist[executionIndex][thread]:
                sys.stdout.write("R%d" % (registerIndex))
                for loadValue in hist[executionIndex][thread][registerIndex]:
                    sys.stdout.write(" %X" % (loadValue))
                sys.stdout.write("\n")

############################################################
## Build dependency lists
############################################################

# NOTE: This algorithm should be somewhat similar to topological sort
#       Whenever a cyclic dependency is found, it terminates with an error

## 1. Intra-thread dependency list
# intraSet is 2-dim dictionary with sets (storing list of dependent instructions): indices are [thread][inst]
intraSet = dict()
for thread in intra:
    intraSet[thread] = dict()
    for inst in intra[thread]:
        intraSet[thread][inst] = set()
        for depInstIndex in intra[thread][inst]:
            intraSet[thread][inst].add(instruction.getMemOp(thread, depInstIndex))

if (verbosity > 1):
    print("### Intra-thread dependencies before propagation")
    for thread in intraSet:
        print("Thread %d" % (thread))
        for inst in intraSet[thread]:
            print("Instruction %d: %s" % (inst, intraSet[thread][inst]))

# dependency propagation
intraSet = setDependencyPropagation(intraSet)

if (verbosity > 1):
    print("### Intra-thread dependencies propagated")
    for thread in intraSet:
        print("Thread %d" % (thread))
        for inst in intraSet[thread]:
            print("Instruction %d: %s" % (inst, intraSet[thread][inst]))

## 2. Inter-thread dependency list
for executionIndex in hist:
    if (verbosity > 0):
        print("%s: Cycle-checking execution %d" % (__file__, executionIndex))
    # Copy intraSet to combinedSet
    combinedSet = dict()
    for thread in intraSet:
        combinedSet[thread] = dict()
        for inst in intraSet[thread]:
            combinedSet[thread][inst] = set()
            for depInst in intraSet[thread][inst]:
                #print("debug: thread %d depInst %d" % (thread, depInst))
                combinedSet[thread][inst].add(depInst)

    if (verbosity > 1):
        print("### Inter dependencies before propagation")
        for thread in hist[executionIndex]:
            print("Thread %d: %s" % (thread, hist[executionIndex][thread]))

    # Add inter-thread dependencies
    for thread in hist[executionIndex]:
        for registerIndex in hist[executionIndex][thread]:
            for loadIndex in range(len(hist[executionIndex][thread][registerIndex])):
                # A (store) -> B (load)
                loadValue = hist[executionIndex][thread][registerIndex][loadIndex]
                instIndex = lookupInstFromLoad[thread][registerIndex][loadIndex]
                aThreadIndex = instruction.getThreadIndex(loadValue)
                aInstIndex = instruction.getInstIndex(loadValue)
                if (not args.single_copy_atomicity and aThreadIndex == thread):
                    # Load value is from a store in the same thread
                    # This dependency is ignored in multiple-copy atomicity...
                    continue
                # Reads-from dependency
                if (aThreadIndex != 0xffff):
                    # find which load instruction corresponds to this load index
                    assert(loadIndex < len(lookupInstFromLoad[thread][registerIndex]))
                    combinedSet[thread][instIndex].add(loadValue)  # NOTE: loadValue should be generated via getMemOp()
                    #print("inter-dependency added: thread %d inst %d -> load value %X" % (thread, instIndex, loadValue));
                # From-reads dependency (see create_dot_graph.py for similar code)
                address = instruction.getAddress(prog[thread][instIndex])
                loadMemOp = instruction.getMemOp(thread, instIndex)
                if (aThreadIndex != 0xffff):
                    if (address in writeOrder[aThreadIndex]):
                        woIdx = writeOrder[aThreadIndex][address].index(aInstIndex)
                        if (woIdx < len(writeOrder[aThreadIndex][address])-1):
                            # A is not last store to the address
                            frInstIndex = writeOrder[aThreadIndex][address][woIdx+1]
                            combinedSet[aThreadIndex][frInstIndex].add(loadMemOp)
                            #print("frDep: %X -> %X -> %X" % (loadValue, loadMemOp, instruction.getMemOp(aThreadIndex, frInstIndex)))
                        else:  # A is the last store
                            pass
                else:
                    for frThreadIndex in combinedSet:
                        if (address in writeOrder[frThreadIndex]):
                            frInstIndex = writeOrder[frThreadIndex][address][0]
                            combinedSet[frThreadIndex][frInstIndex].add(loadMemOp)
                            #print("frDep: %X -> %X -> %X" % (loadValue, loadMemOp, instruction.getMemOp(frThreadIndex, frInstIndex)))

    # dependency propagation
    combinedSet = setDependencyPropagation(combinedSet)

    if (verbosity > 1):
        print("### Inter+Intra dependencies propagated")
        for thread in combinedSet:
            print("Thread %d" % (thread))
            for inst in combinedSet[thread]:
                print("Instruction %d: %s" % (inst, combinedSet[thread][inst]))

    # debug
    #sys.exit(0)


