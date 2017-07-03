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

# Generate graph (.dot) files from program (static information) and history of load values (dynamic information)

import os
import sys
import argparse
import instruction
import parse_prog
import parse_hist

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--out-dir", help="directory to save individual log files", default="log")
parser.add_argument("--program-file", "-p", help="intermediate file that describes test program and intra-thread dependency", default="prog.txt")
parser.add_argument("--wo-file", help="intermediate write-order file name", default="wo.txt")
parser.add_argument("--gen-png", action="store_true", help="generate PNG files for graphs", default=False)
parser.add_argument("--gen-tsort", action="store_true", help="generate graph description files for Linux tsort program in Coreutils", default=False)
parser.add_argument("--ignore-reg", action="store_true", default=False)
parser.add_argument("--no-dot", action="store_true", default=False)
parser.add_argument("--single-copy-atomicity", action="store_true", default=False)
parser.add_argument("inputs", metavar="history summary files", nargs="+", help="history files to be processed")
args = parser.parse_args()

verbosity = args.verbose

if (args.out_dir == None):
    outDirPrefix = "."
elif (args.out_dir[-1] != "/"):
    outDirPrefix = args.out_dir
else: # Remove "/" at the end of string
    outDirPrefix = args.out_dir[:-1]

returnDict = parse_prog.parseProgram(args.program_file, args.wo_file, args.ignore_reg, verbosity)
prog = returnDict["progInfo"]
intra = returnDict["intraDep"]
writeOrder = returnDict["writeOrder"]
lookupInstFromLoad = returnDict["lookupTable"]

hist = parse_hist.parseHistoryFile(args.inputs, verbosity)

#print("prog %s" % prog)
#print("intra %s" % intra)
#print("hist %s" % hist)

numThreads = len(prog)

for executionIndex in hist:
    if (not args.no_dot):
        graphFileName = "%s/graph%d.dot" % (outDirPrefix, executionIndex)
        graphFP = open(graphFileName, "w")
        graphFP.write("digraph mt_mem {\n")
        graphFP.write("node [shape=box];\n")
        graphFP.write("splines = spline;\n")

    if (args.gen_tsort):
        tsortFP = open("%s/tsort%d.txt" % (outDirPrefix, executionIndex), "w")
    else:
        tsortFP = None

    maxInstLen = -1
    for thread in range(numThreads):
        if (len(prog[thread]) > maxInstLen):
            maxInstLen = len(prog[thread])
        for inst in range(len(prog[thread])):
            vertexString = prog[thread][inst]
            if (not args.no_dot):
                graphFP.write("%s [label=\"%s\", pos=\"%d,%d!\"];\n" % (instruction.getMemId(thread, inst), vertexString, thread * 200, (len(prog[thread])-1-inst) * 100))

    for thread in range(numThreads):
        for inst in range(len(prog[thread])):
            # Arrow: A -> B
            aThreadIndex = thread
            bThreadIndex = thread
            bInstIndex = inst
            for aInstIndex in intra[thread][inst]:
                if (not args.no_dot):
                    graphFP.write("%s -> %s [color=\"black\"];\n" % (instruction.getMemId(aThreadIndex, aInstIndex), instruction.getMemId(bThreadIndex, bInstIndex)))
                if (tsortFP != None):
                    tsortFP.write("%s %s\n" % (instruction.getMemId(aThreadIndex, aInstIndex), instruction.getMemId(bThreadIndex, bInstIndex)))
        for registerIndex in hist[executionIndex][thread]:
            for loadIndex in range(len(hist[executionIndex][thread][registerIndex])):
                loadValue = hist[executionIndex][thread][registerIndex][loadIndex]
                #if (instruction.getThreadIndex(loadValue) == 0xffff):
                #    # load value from initial memory values (not from store)
                #    continue
                # find which load instruction corresponds to this load index
                assert(loadIndex < len(lookupInstFromLoad[thread][registerIndex]))
                instIndex = lookupInstFromLoad[thread][registerIndex][loadIndex]
                aThreadIndex = instruction.getThreadIndex(loadValue)
                aInstIndex = instruction.getInstIndex(loadValue)
                bThreadIndex = thread
                bInstIndex = instIndex
                address = instruction.getAddress(prog[bThreadIndex][bInstIndex])
                if (not args.single_copy_atomicity and aThreadIndex == bThreadIndex):
                    # Load value is from a store in the same thread
                    # This dependency is ignored in multiple-copy atomicity...
                    assert(aThreadIndex != 0xffff)
                    if (not args.no_dot):
                        # Draw this edge in a different color in dot graph.
                        graphFP.write("%s -> %s [color=\"cyan\"];\n" % (instruction.getMemId(aThreadIndex, aInstIndex), instruction.getMemId(bThreadIndex, bInstIndex)))
                    if (tsortFP != None):
                        # Dummy reads-from dependency
                        tsortFP.write("i %s\n" % (instruction.getMemId(bThreadIndex, bInstIndex)))
                        # Dummy from-reads dependency
                        for frThreadIndex in range(numThreads):
                            if (frThreadIndex == aThreadIndex):  # A thread
                                if (address in writeOrder[frThreadIndex]):
                                    tsortFP.write("%s t\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex)))
                            else:  # Threads other than A
                                if (address in writeOrder[frThreadIndex]):
                                    tsortFP.write("%s t\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex)))
                    continue
                ## reads-from dependency: A -> B
                if (not args.no_dot):
                    if (aThreadIndex != 0xffff):
                        graphFP.write("%s -> %s [color=\"blue\"];\n" % (instruction.getMemId(aThreadIndex, aInstIndex), instruction.getMemId(bThreadIndex, bInstIndex)))
                if (tsortFP != None):
                    if (aThreadIndex != 0xffff):
                        tsortFP.write("%s %s\n" % (instruction.getMemId(aThreadIndex, aInstIndex), instruction.getMemId(bThreadIndex, bInstIndex)))
                    else:
                        tsortFP.write("i %s\n" % (instruction.getMemId(bThreadIndex, bInstIndex)))
                ## from-reads dependency: B -> A.[from-reads dependency]
                if (not args.no_dot):
                    if (aThreadIndex != 0xffff):
                        if (address in writeOrder[aThreadIndex]):
                            woIdx = writeOrder[aThreadIndex][address].index(aInstIndex)
                            if (woIdx < len(writeOrder[aThreadIndex][address])-1):
                                # A is not last store to the address
                                frInstIndex = writeOrder[aThreadIndex][address][woIdx+1]
                                graphFP.write("%s -> %s [color=\"green\"];\n" % \
                                    (instruction.getMemId(bThreadIndex, bInstIndex), instruction.getMemId(aThreadIndex, frInstIndex)))
                            else:  # A is the last store
                                pass
                    else:
                        for frThreadIndex in range(numThreads):
                            if (address in writeOrder[frThreadIndex]):
                                frInstIndex = writeOrder[frThreadIndex][address][0]
                                graphFP.write("%s -> %s [color=\"green\"];\n" % \
                                    (instruction.getMemId(bThreadIndex, bInstIndex), instruction.getMemId(frThreadIndex, frInstIndex)))
                if (tsortFP != None):
                    for frThreadIndex in range(numThreads):
                        if (frThreadIndex == aThreadIndex):  # A thread
                            if (address in writeOrder[frThreadIndex]):
                                woIdx = writeOrder[frThreadIndex][address].index(aInstIndex)
                                if (woIdx < len(writeOrder[frThreadIndex][address])-1):  # A is not last store to the address
                                    frInstIndex = writeOrder[aThreadIndex][address][woIdx+1]
                                    tsortFP.write("%s %s\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex), instruction.getMemId(frThreadIndex, frInstIndex)))
                                else:  # A is the last store
                                    tsortFP.write("%s t\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex)))
                        else:  # Threads other than A
                            if (address in writeOrder[frThreadIndex]):
                                if (aThreadIndex == 0xffff):
                                    tsortFP.write("%s %s\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex), \
                                        (instruction.getMemId(frThreadIndex, writeOrder[frThreadIndex][address][0]))))
                                else:
                                    tsortFP.write("%s t\n" % \
                                        (instruction.getMemId(bThreadIndex, bInstIndex)))

    if (not args.no_dot):
        for inst in range(maxInstLen):
            graphFP.write("{ rank = same;")
            for thread in range(numThreads):
                graphFP.write(" %s;" % (instruction.getMemId(thread, inst)))
            graphFP.write(" }\n")
        graphFP.write("}\n")
        graphFP.close()

    if (tsortFP != None):
        tsortFP.close()

    if (args.gen_png):
        os.system("neato -n -Tpng %s/graph%d.dot -o%s/graph%d.png" % (outDirPrefix, executionIndex, outDirPrefix, executionIndex))

if (args.gen_tsort):
    tsortListFP = open("%s/tsort_list.txt" % (outDirPrefix), "w")
    for executionIndex in hist:
        tsortListFP.write("%s/tsort%d.txt\n" % (outDirPrefix, executionIndex))
    tsortListFP.close()

