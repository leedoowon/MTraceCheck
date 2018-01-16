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

#
# This code generates and executes fully random multi-threaded
# test program under given memory ordering model, and
# outputs resulting constraint & dependency graph in .dot file.
#

import os
import sys
import random
import argparse
import instruction

#
# Generation-time per-address store identifier
#
# FIXME: Currently, the implementation uses 'global' store identifiers,
#        unique to each store operation.
#
# NOTE: Workaround - global store identifiers can be considered as
#       per-address identifier, as long as the number of store operations
#       does not exceed the limited bit-width (e.g., 8-bit) used for
#       storing each identifier. Thus, currently, the implementation
#       simply uses global identifiers as if they are per-address
#       identifiers.
#       Instead, an additional mapping table limiting the number of
#       store identfiers to correctly mimic the bit-width would need
#       in order not to generate store operations more than allowed.
#       For instance, if the bit-width of a per-address identifier is
#       8 bits, then there should be only 256 store operations allowed
#       across all threads. Generation of more than 256 operations
#       should be limited.
#

#
# Store/Load address allocation
#
# NOTE: This is fairly critical, as we can store only a recent history of
#       accesses for each address. As test length increases, there could be
#       a large masking possible in the beginning of the test.
# NOTE: Research possibility - how to encode/decode the access patterns
#       under the limited tracing capability. This process should be quick.
#

#
# Compressing store identifiers
#
# NOTE: Use underlying memory ordering rules. This will be only effective
#       for strong memory ordering rules such as SC and TSO.
#

#
# From-read edges
#
# FIXME: These edges should be accounted as follows.
#  If a read A takes the value of a store B in thread K,
#  then for stores C1, C2, ... with the same address as B in K,
#  there should be coherence edges from A to those stores (C1, C2, ...).
# NOTE: This has been lightly implemented in Oct 18, 2016.
#       But memory barrier operations are not handled properly until then.
#

#
# doowon, 2017/09/06, fences added
#
# FIXME: Edges from/to fences need to be verified if the current implemention are strong enough
#
#


#def printUsage():
#    print("Usage: python %s [# threads] [# instructions] [# memory locations] [# outstanding ops]" % (__file__))

class RandomInteger():

    def __init__(self, paramLower=0):
        self.lower = paramLower
        self.upper = paramLower
        self.binType = -1
        self.bins = []
        self.numBins = 0

    def setBinType(self, paramBinType):
        assert(paramBinType == 0 or paramBinType == 1)
        self.binType = paramBinType

    def addBin(self, frequency, value):
        assert(self.binType != -1)
        assert(frequency >= 1)
        # binMin <= N < binMax
        binMin = self.upper
        binMax = self.upper + frequency
        self.upper = binMax
        self.bins.append([binMin, binMax, value])
        self.numBins = self.numBins + 1

    def genRand(self):
        randInt = random.randint(self.lower, self.upper-1)  # self.lower <= N < self.upper
        for binIdx in range(self.numBins):
            if ((self.bins[binIdx][0] <= randInt) and (self.bins[binIdx][1] > randInt)):
                if (self.binType == 0):
                    return self.bins[binIdx][2]
                elif (self.binType == 1):
                    return self.bins[binIdx][2] + (randInt - self.bins[binIdx][0])
        # Index not found
        print("Error: Random value %d is not found from RandomInteger class (lower bound %d, upper bound %d)" % (randInt, self.lower, self.upper-1))
        sys.exit(1)

    def printBins(self):
        assert(self.numBins == len(self.bins))
        print("Print bins of type %d..." % (self.binType))
        for binIdx in range(self.numBins):
            print(self.bins[binIdx])


############################################################
## Processing command line arguments
############################################################
#if (len(sys.argv) != 5):
#    printUsage()
#    sys.exit(1)

#try:
#    numThreads = int(sys.argv[1])
#    numInsts = int(sys.argv[2])
#    numMemLocs = int(sys.argv[3])
#    numOutstandingOps = int(sys.argv[4])
#except:
#    printUsage()
#    sys.exit(1)

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--rand-seed", type=int, help="random seed", default=894291)
parser.add_argument("--threads", "-t", type=int, help="number of threads to be generated", default=2)
parser.add_argument("--insts", "-i", type=int, help="number of memory operations to be generated for each thread", default=10)
parser.add_argument("--locs", "-l", type=int, help="number of memory target locations", default=4)
parser.add_argument("--outstanding", "-o", type=int, help="number of outstanding memory operations for each thread (-1: entire range)", default=-1)
parser.add_argument("--execs", "-e", type=int, help="number of executions", default=10)
parser.add_argument("--hist-regs", type=int, help="number of registers to save loaded value", default=16)
parser.add_argument("--hist-per-reg", type=int, help="number of loaded values per history register (-1: unlimited)", default=-1)
parser.add_argument("--log-dir", help="directory to save individual log files", default="log")
parser.add_argument("--summary-dir", help="directory to save summary files (e.g., md5 hashes)", default=None)
parser.add_argument("--consistency-model", help="consistency model", default="sc")
parser.add_argument("--single-copy-atomicity", action="store_true", default=False)
parser.add_argument("--gen-program", action="store_true", help="generate intermediate file that represents a generated multi-threaded program, with intra-thread dependency annotated", default=False)
parser.add_argument("--prog-file", help="intermediate program file name", default="prog.txt")
parser.add_argument("--wo-file", help="intermediate write-order file name", default="wo.txt")
parser.add_argument("--no-dump-files", action="store_true", help="do not generate memory dump files", default=False)
parser.add_argument("--with-fences", action="store_true", default=False)
args = parser.parse_args()

verbosity = args.verbose
numThreads = args.threads
numInsts = args.insts
numMemLocs = args.locs
if (args.outstanding == -1):
    numOutstandingOps = args.insts
else:
    numOutstandingOps = args.outstanding
numExecutions = args.execs
numHistRegs = args.hist_regs
numHistPerReg = args.hist_per_reg
if (args.log_dir == None):
    logDirPrefix = "."
elif (args.log_dir[-1] != "/"):
    logDirPrefix = args.log_dir
else: # Remove "/" at the end of string
    logDirPrefix = args.log_dir[:-1]
if (args.summary_dir == None):
    summaryDirPrefix = "."
elif (args.summary_dir[-1] != "/"):
    summaryDirPrefix = args.summary_dir
else:
    summaryDirPrefix = args.summary_dir[:-1]

if not os.path.exists(logDirPrefix):
    os.makedirs(logDirPrefix)
if not os.path.exists(summaryDirPrefix):
    os.makedirs(summaryDirPrefix)

#print("debug: numOutstandingOps %d" % numOutstandingOps)

############################################################
## Script initialization
############################################################

random.seed(args.rand_seed)

## Define reordering constraints for simulation
if (args.consistency_model == "sc"):
    # Sequential consistency (SC)
    orderLdLd = True
    orderLdSt = True
    orderStLd = True
    orderStSt = True
elif (args.consistency_model == "tso"):
    # Total store ordering (TSO)
    orderLdLd = True
    orderLdSt = True
    orderStLd = False
    orderStSt = True
elif (args.consistency_model == "ro"):
    # Relaxed ordering (RO)
    orderLdLd = False
    orderLdSt = False
    orderStLd = False
    orderStSt = False
elif (args.consistency_model == "wo"):
    # Weak ordering (WO)
    orderLdLd = False
    orderLdSt = False
    orderStLd = False
    orderStSt = False
else:
    print("Error: Unrecognized consistency model %s" % args.consistency_model)

if (verbosity > 0):
    print("Memory consistency model %s" % (args.consistency_model))

############################################################
## Generate random test program
############################################################

## Not sure how the memory ordering problem can be accurately embedded in randomized tests

## How to abstract the behavior of memory operations
# System abstraction: Core <-> Memory
# Two types of operation: load and store
# Load: Memory -> Core
# Store: Core -> Memory
# Consider memory as a big storage... No operation is performed except for data transfer (possibly among threads)

# Every data source should be either from initial value of memory, or stored value

## Type of instruction: load (0), store (1), fence (2)
randInstType = RandomInteger()
randInstType.setBinType(0)
if (args.with_fences):
    ## doowon, 2017/09/06, fences are included in generated test with the probability of 2%
    # TODO: Flexible percentages
    randInstType.addBin(49, 0)  # 49%, 0 (load)
    randInstType.addBin(49, 1)  # 49%, 1 (store)
    randInstType.addBin( 2, 2)  #  2%, 2 (fence)
else:
    randInstType.addBin(50, 0)  # 50%, 0 (load)
    randInstType.addBin(50, 1)  # 50%, 1 (store)
if (verbosity > 0):
    randInstType.printBins()

## Random number generator for addresses
# Memory addresses are generated fully randomly, without considering previous addresses
randAddress = RandomInteger()  # Memory address: 0 -- (numMemLocs-1) with equal probability
randAddress.setBinType(1)
randAddress.addBin(numMemLocs, 0)
if (verbosity > 0):
    randAddress.printBins()

## Random number generator for load targets
randLoadTarget = RandomInteger()  # Load target: 0 -- (numHistRegs-1) e.g., r0 -- r15
randLoadTarget.setBinType(1)
randLoadTarget.addBin(numHistRegs, 0)
if (verbosity > 0):
    randLoadTarget.printBins()

insts = [[] for i in range(numThreads)]

for thread in range(numThreads):
    for inst in range(numInsts):
        instType = randInstType.genRand()
        address = randAddress.genRand()
        loadTarget = randLoadTarget.genRand()
        currInst = instruction.Instruction(instType, address, loadTarget)
        insts[thread].append(currInst)

# Print generated instructions
if (verbosity > 0):
    print("### Printing generated instructions")
    for thread in range(numThreads):
        print("Thread %d" % (thread))
        for inst in range(len(insts[thread])):
            insts[thread][inst].printInst()


############################################################
## Create constraint edges (intra-thread)
############################################################

## Memory reordering rules (either different or same address)
for thread in range(numThreads):
    lastLdIndex = -1
    lastStIndex = -1
    lastFenceIndex = -1
    # FIXME: intra dependency edges from/to fences
    for inst in range(len(insts[thread])):
        if (insts[thread][inst].instType == 0):  # if instType == LOAD
            if (orderLdLd and lastLdIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastLdIndex))
            if (orderStLd and lastStIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastStIndex))
            if (lastFenceIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastFenceIndex))
            lastLdIndex = inst
        elif (insts[thread][inst].instType == 1):  # if instType == STORE
            if (orderLdSt and lastLdIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastLdIndex))
            if (orderStSt and lastStIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastStIndex))
            if (lastFenceIndex != -1):
                insts[thread][inst].addIntraDep(instruction.getMemOp(thread, lastFenceIndex))
            lastStIndex = inst
        elif (insts[thread][inst].instType == 2):  # if instType == FENCE
            # NOTE: dependency to this fence will be created in the next for loop
            lastFenceIndex = inst
        else:
            print ("Error: Unrecognized instruction type %d" % insts[thread][inst].instType)
    reverseLastFenceIndex = -1
    for inst in reversed(range(len(insts[thread]))):
        if (insts[thread][inst].instType == 0):  # if instType == LOAD
            if (reverseLastFenceIndex != -1):
                insts[thread][reverseLastFenceIndex].addIntraDep(instruction.getMemOp(thread, inst))
        elif (insts[thread][inst].instType == 1):  # if instType == STORE
            if (reverseLastFenceIndex != -1):
                insts[thread][reverseLastFenceIndex].addIntraDep(instruction.getMemOp(thread, inst))
        elif (insts[thread][inst].instType == 2):  # if instType == FENCE
            if (reverseLastFenceIndex != -1):
                insts[thread][reverseLastFenceIndex].addIntraDep(instruction.getMemOp(thread, inst))
            reverseLastFenceIndex = inst
        else:
            print ("Error: Unrecognized instruction type %d" % insts[thread][inst].instType)
    # Avoid using these temporary variables accidentally later on
    del lastLdIndex
    del lastStIndex
    del lastFenceIndex
    del reverseLastFenceIndex

## Program order (same address)
# This code assumes cache coherency by creating edges for same address for:
# (1) store->store
# (2) (last) store->load
#
# NOTE: This is now enabled optionally, depending on single-copy atomicity flag
#
if (args.single_copy_atomicity):
    for thread in range(numThreads):
        for instA in range(len(insts[thread])-1): # For each A for A->B edges
            if (insts[thread][instA].instType == 1):  # if instType == STORE
                addressA = insts[thread][instA].address
                for instB in range(instA+1, len(insts[thread])):
                    addressB = insts[thread][instB].address
                    if (insts[thread][instB].instType == 0 and addressB == addressA):  # if instType == LOAD with same address (case (2) above)
                        insts[thread][instB].addIntraDep(instruction.getMemOp(thread, instA))
                    elif (insts[thread][instB].instType == 1 and addressB == addressA):  # if instType == STORE with same address (case (1) above)
                        insts[thread][instB].addIntraDep(instruction.getMemOp(thread, instA))
                        # Instruction B should be the source for next instructions (no further check)
                        break
                    # FIXME: Need to consider additional types of instructions?
            # No other types (e.g., LOAD) need to be considered

############################################################
## Write the generated program and intra-thread dependency in an intermediate file
############################################################

# Instructions will be identified by an ID assigned to each instruction,
# An ID contains (1) thread index and (2) instruction index within thread.

## Intermediate file format
# 1. Each line corresponds to an instruction
# 2. Each line contains: [thread index]%[instruction index]%[assembly code](%[dependent instruction])*
""" Intermediate file example
0/0#ld 0x3,r9
0/1#st 0x2#0
0/2#ld 0x2,r10#0#1
"""

if (args.gen_program):
    progFileName = "%s/%s" % (summaryDirPrefix, args.prog_file)
    woFileName = "%s/%s" % (summaryDirPrefix, args.wo_file)
    progFP = open(progFileName, "w")
    woFP = open(woFileName, "w")
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            instructionLine = "%d/%d#%s" % (thread, inst, insts[thread][inst].getAssembly())
            for intraDep in insts[thread][inst].intraDeps:
                intraDepInstIndex = instruction.getInstIndex(intraDep)
                instructionLine += ("#%d" % (intraDepInstIndex))
            instructionLine += "\n"
            progFP.write(instructionLine)
        if (orderStSt):
            # doowon, 2017/09/06, FIXME: Write order needs to handle fences
            woDict = dict()
            for inst in range(len(insts[thread])):
                # [thread id]/[memory location]#[inst idx 1]#[inst idx 2]#...
                # No line if memory location is not used at all
                if (insts[thread][inst].instType == 1):
                    address = insts[thread][inst].address
                    assert(address != -1)
                    if (not address in woDict):
                        woDict[address] = [inst]
                    else:
                        woDict[address].append(inst)
            for address in woDict:
                woLine = "%d/0x%X" % (thread, address)
                for inst in woDict[address]:
                    woLine += "#%d" % (inst)
                woLine += "\n"
                woFP.write(woLine)
    progFP.close()
    woFP.close()

############################################################
## Execution iteration loop
############################################################
if (not args.no_dump_files):
    dumpSummaryFileName = "%s/dump.txt" % (summaryDirPrefix)
    dumpSummaryFP = open(dumpSummaryFileName, "w")
histSummaryFileName = "%s/hist.txt" % (summaryDirPrefix)
histSummaryFP = open(histSummaryFileName, "w")

for executionIndex in range(numExecutions):

    if (verbosity > 0):
        print("Execution %d" % executionIndex)
        #if ((executionIndex % 100) == 1):
        #    print("Execution %d" % executionIndex)

    ############################################################
    ## Initialization
    ############################################################

    ## Initialize instruction state
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            insts[thread][inst].resetInst()

    ## Initialize memory locations with their address
    mem = []
    for i in range(numMemLocs):
        initDataValue = instruction.getMemOp(0xffff, i)
        mem.append(initDataValue)

    ## Initialize load-target register
    historyLoadTargets = [[[] for i in range(numHistRegs)] for j in range(numThreads)]

    ## Initialize instruction scheduling window
    # NOTE: This code does not take into account separate queues for load and store

    schedWindows = []
    readyQueues = []
    nextQueueInsts = []
    for thread in range(numThreads):
        threadInstWindow = []
        threadReadyQueue = []
        for instIndex in range(min(numOutstandingOps, len(insts[thread]))):
            isReady = True
            for intraDep in insts[thread][instIndex].intraDeps:
                intraDepInstIndex = instruction.getInstIndex(intraDep)
                if (insts[thread][intraDepInstIndex].exeState != instruction.ExecutionState.PERFORMED):
                    isReady = False
                    break
            if (isReady):
                insts[thread][instIndex].exeState = instruction.ExecutionState.READY
                threadReadyQueue.append(instIndex)
            else:
                insts[thread][instIndex].exeState = instruction.ExecutionState.WAIT
            threadInstWindow.append(instIndex)
        schedWindows.append(threadInstWindow)
        readyQueues.append(threadReadyQueue)
        nextQueueInsts.append(min(numOutstandingOps, len(insts[thread])))

    ## Cache coherency (same-address rule) is taken into account by default
    # This is done by maintaining a global 'mem' storage, which can be seen
    # by all threads.

    ## NOTE: Single-copy, multiple-copy, non-multiple-copy atomic stores should
    # be considered in some way. Currently, the code assumes single-copy atomicity.
    # Taking into account multiple-copy and non-multiple-copy atomic stores can be
    # done by having multiple instances of 'mem' storages.

    ## NOTE: This version of code does not accommodate transitivity, generating
    # all operation-to-operation dependency.

    ############################################################
    ## Execute test program
    ############################################################

    unfinishedThreadList = [i for i in range(numThreads)]

    while (len(unfinishedThreadList) > 0):
        ## Choose a thread to execute
        randInt = random.randint(0, len(unfinishedThreadList)-1)  # 0 <= randInt < len(unfinishedThreadList)
        thread = unfinishedThreadList[randInt]
        if (args.debug):
            print("debug: thread random integer %d" % (randInt))

        ## Choose an instruction to execute
        randInt = random.randint(0, len(readyQueues[thread])-1)  # 0 <= randInt < len(readyQueues[thread])
        inst = readyQueues[thread][randInt]
        if (args.debug):
            print("debug: instruction random integer %d" % (randInt))

        ## Print verbose & debug messages
        if (verbosity > 1):
            print("Execute: thread %d inst %d (%s)" % (thread, inst, insts[thread][inst].getAssembly()))

        ## Execute the instruction
        # 1. Update loaded value (load) or mem (store)
        if (insts[thread][inst].instType == 0):  # if instType == LOAD
            loadAddress = insts[thread][inst].address
            insts[thread][inst].writeValue(mem[loadAddress])
        elif (insts[thread][inst].instType == 1):  # if instType == STORE
            storeAddress = insts[thread][inst].address
            mem[storeAddress] = instruction.getMemOp(thread, inst)
        elif (insts[thread][inst].instType == 2):  # if instType == FENCE
            # Fences do not have any effect in registers or memory
            pass

        # 2. Update instruction execution status
        insts[thread][inst].exeState = instruction.ExecutionState.PERFORMED

        # 2.1. Update load-value history
        if (insts[thread][inst].instType == 0):  # if instType == LOAD
            loadAddress = insts[thread][inst].address
            targetIndex = insts[thread][inst].loadTarget
            loadValue = mem[loadAddress]
            historyLoadTargets[thread][targetIndex].append(loadValue)

        # 3. Update ready queue
        readyQueues[thread].remove(inst)

        # 4. Update instruction window
        # 4.1. Remove current instruction from instruction window
        schedWindows[thread].remove(inst)

        # 4.2. Change state of instructions in scheduling window
        for candInst in schedWindows[thread]:
            isReady = True
            for intraDep in insts[thread][candInst].intraDeps:
                intraDepInstIndex = instruction.getInstIndex(intraDep)
                if (insts[thread][intraDepInstIndex].exeState != instruction.ExecutionState.PERFORMED):
                    isReady = False
                    break
            if (args.debug):
                print("thread %d candInst %d ready %d" % (thread, candInst, isReady))
            if (isReady and insts[thread][candInst].exeState == instruction.ExecutionState.WAIT):
                insts[thread][candInst].exeState = instruction.ExecutionState.READY
                readyQueues[thread].append(candInst)

        # 4.3. Add next instruction to instruction window
        if (nextQueueInsts[thread] < len(insts[thread])):
            nextInst = nextQueueInsts[thread]
            isReady = True
            for intraDep in insts[thread][nextInst].intraDeps:
                intraDepInstIndex = instruction.getInstIndex(intraDep)
                if (insts[thread][intraDepInstIndex].exeState != instruction.ExecutionState.PERFORMED):
                    isReady = False
                    break
            if (isReady):
                insts[thread][nextInst].exeState = instruction.ExecutionState.READY
                readyQueues[thread].append(nextInst)
            else:
                insts[thread][nextInst].exeState = instruction.ExecutionState.WAIT
            schedWindows[thread].append(nextInst)
            nextQueueInsts[thread] = nextInst + 1

        # 5. Check for thread end
        if (len(readyQueues[thread]) == 0):
            unfinishedThreadList.remove(thread)


    ############################################################
    ## Create dependency edges (inter-thread)
    ############################################################

    ## Inter-thread dependency (dependency edges)
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            if (insts[thread][inst].instType == 0):  # if instType == LOAD
                # Arrow: A -> B
                if (insts[thread][inst].value == 0xffffffff):
                    print("Warning: Load instruction at thread %d instruction %d has invalid load value %d" % (thread, inst, insts[thread][inst].value))
                else:
                    insts[thread][inst].addInterDep(insts[thread][inst].value)

    ############################################################
    ## Check for cycles (topological sorting)
    ############################################################
    ## Construct set of incoming edges for each instruction
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            for intraDep in insts[thread][inst].intraDeps:
                aThreadIndex = instruction.getThreadIndex(intraDep)
                aInstIndex = instruction.getInstIndex(intraDep)
                if (aThreadIndex != 0xffff):
                    insts[thread][inst].addSortEdge(instruction.getMemOp(aThreadIndex, aInstIndex))
                    insts[aThreadIndex][aInstIndex].addReverseEdge(instruction.getMemOp(thread, inst))
            for interDep in insts[thread][inst].interDeps:
                aThreadIndex = instruction.getThreadIndex(interDep)
                aInstIndex = instruction.getInstIndex(interDep)
                if (aThreadIndex != 0xffff):
                    insts[thread][inst].addSortEdge(instruction.getMemOp(aThreadIndex, aInstIndex))
                    insts[aThreadIndex][aInstIndex].addReverseEdge(instruction.getMemOp(thread, inst))

    ## Initialization: pop instructions with no incoming edges, and put them into a list
    waitQueue = []
    sortQueue = []
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            if (insts[thread][inst].sortOrder == None and len(insts[thread][inst].sortEdges) == 0):
                currMemOp = instruction.getMemOp(thread, inst)
                waitQueue.append(currMemOp)

    #print("Debug: waitQueue pop")

    ## Iteration: pop the first instruction from the list, remove connected edges, and puts adjacent nodes if they have no incoming edges
    while len(waitQueue) > 0:
        currMemOp = waitQueue.pop()
        currThreadIndex = instruction.getThreadIndex(currMemOp)
        currInstIndex = instruction.getInstIndex(currMemOp)
        insts[currThreadIndex][currInstIndex].sortOrder = len(sortQueue)
        sortQueue.append(currMemOp)
        # debug
        #print("Thread %d Inst %d" % (currThreadIndex, currInstIndex))
        for bMemOp in insts[currThreadIndex][currInstIndex].sortReverseEdges:
            bThreadIndex = instruction.getThreadIndex(bMemOp)
            bInstIndex = instruction.getInstIndex(bMemOp)
            insts[bThreadIndex][bInstIndex].removeSortEdge(currMemOp)
            if (insts[bThreadIndex][bInstIndex].sortOrder == None and len(insts[bThreadIndex][bInstIndex].sortEdges) == 0):
                nextMemOp = instruction.getMemOp(bThreadIndex, bInstIndex)
                waitQueue.append(nextMemOp)

    ## Check for cycle
    orderDefined = True
    for thread in range(numThreads):
        for inst in range(len(insts[thread])):
            if (insts[thread][inst].sortOrder == None):
                orderDefined = False
                break
        if (not orderDefined):
            break

    if (verbosity > 1):
        if (orderDefined):
            print("(Exec%d) INFO: Cycle undetected" % (executionIndex))
        else:
            print("(Exec%d) INFO: Cycle detected!!!" % (executionIndex))

    ############################################################
    ## Generate output: memory dump
    ############################################################
    if (not args.no_dump_files):
        stringToWrite = ""
        for i in range(numMemLocs):
            stringToWrite += ("%08x\n" % mem[i])

        dumpFileName = "%s/dump%d.txt" % (logDirPrefix, executionIndex)
        dumpFP = open(dumpFileName, "w")
        dumpFP.write(stringToWrite)
        dumpFP.close()

        dumpSummaryFP.write("### Execution %d\n" % (executionIndex))
        dumpSummaryFP.write(stringToWrite)

    ############################################################
    ## Generate output: load target history
    ############################################################
    stringToWrite = "### Execution %d\n" % (executionIndex)
    if (numHistPerReg > 0):
        for thread in range(numThreads):
            for target in range(numHistRegs):
                historyLoadTargets[thread][target] = historyLoadTargets[thread][target][-(numHistPerReg):]
    else:
        assert(numHistPerReg == -1)
        # Unlimited collection of values
    for thread in range(numThreads):
        stringToWrite += ("T%d:" % (thread))
        for target in range(numHistRegs):
            stringToWrite += (" %d-" % (target))
            for loadIndex in range(len(historyLoadTargets[thread][target])):
                if (loadIndex != 0):
                    stringToWrite += (",%X" % historyLoadTargets[thread][target][loadIndex])
                else:
                    stringToWrite += ("%X" % historyLoadTargets[thread][target][loadIndex])
        stringToWrite += "\n"

    histFileName = "%s/hist%d.txt" % (logDirPrefix, executionIndex)
    histFP = open(histFileName, "w")
    histFP.write(stringToWrite)
    histFP.close()

    histSummaryFP.write(stringToWrite)

if (not args.no_dump_files):
    dumpSummaryFP.close()
histSummaryFP.close()

