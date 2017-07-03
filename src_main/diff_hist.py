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
import random
import argparse
import parse_hist

# Compare types
COMPARE_BASELINE = 0
COMPARE_ADJACENT = 1

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--rand-seed", type=int, help="random seed", default=894291)
parser.add_argument("--compare", "-c", default="baseline")
parser.add_argument("--baseline", "-b", default="0")
parser.add_argument("--print-stdout", action="store_true", default=False)
parser.add_argument("--gen-csv", action="store_true", default=False)
parser.add_argument("--kmedoids", action="store_true", default=False)
parser.add_argument("--nummedoids", type=int, default=2)
parser.add_argument("--percenttrials", type=int, default=10)  # 10% by default
parser.add_argument("inputs", metavar="history files", nargs="+", help="history files to be processed")
args = parser.parse_args()

verbosity = args.verbose
if (args.compare == "baseline"):
    compareType = COMPARE_BASELINE
elif (args.compare == "adjacent"):
    compareType = COMPARE_ADJACENT
else:
    print("Error: Unrecognized argument %s" % (args.compare))
    sys.exit(1)

if (compareType == COMPARE_BASELINE):
    # parse baseline indices
    # e.g., --baseline=0,2-4,10
    baselineList = []
    indexRanges = args.baseline.split(",")
    for eachIndexRange in indexRanges:
        rangeMinMax = eachIndexRange.split("-")
        if (len(rangeMinMax) == 1):
            baselineList.append(int(rangeMinMax[0]))
        elif (len(rangeMinMax) == 2):
            minIndex = int(rangeMinMax[0])
            maxIndex = int(rangeMinMax[1]) + 1
            for i in range(minIndex, maxIndex):
                baselineList.append(i)
    assert(len(baselineList) >= 1)
    if (verbosity > 0):
        print("INFO: Comparison type %d" % (compareType))
        if (verbosity > 1):
            if (len(baselineList) == 1):
                print("(baseline: %d)" % (baselineList[0]))
            else:
                print("(baselines: %s)" % (baselineList))
elif (compareType == COMPARE_ADJACENT):
    if (verbosity > 0):
        print("INFO: Comparison type %d" % (compareType))
    print("ERROR: Currently not fully implemented")  # FIXME
    assert(False)
# NOTE: Add here when you add additional types of comparisons in the future

############################################################
## Parse the history log file
############################################################

hist = parse_hist.parseHistoryFile(args.inputs, verbosity)

# debug
if args.debug:
    for executionIndex in hist:
        for threadIndex in hist[executionIndex]:
            sys.stdout.write("Execution %d T%d" % (executionIndex, threadIndex))
            sys.stdout.write("\n")
            for registerIndex in hist[executionIndex][threadIndex]:
                sys.stdout.write("R%d" % (registerIndex))
                for loadValue in hist[executionIndex][threadIndex][registerIndex]:
                    sys.stdout.write(" %X" % (loadValue))
                sys.stdout.write("\n")


############################################################
## Diffing two executions: execution A (baseline) vs execution B
############################################################
mismatchCountAll = dict()
for baselineIndex in baselineList:
    mismatchCountBase = dict()
    assert(baselineIndex in hist)  # baselineIndex is the index of base execution (A)
    if verbosity > 0:
        print("## Baseline Index: %d" % baselineIndex)
    # NOTE: Multiple executions of a same program, thus same number of threads, registers, loaded values
    for executionIndex in hist:
        mismatchCountBase[executionIndex] = 0
        if (executionIndex == baselineIndex):
            continue
        if verbosity > 1:
            print("# Comparing %d (baseline %d)" % (executionIndex, baselineIndex))
        histA = hist[baselineIndex]
        histB = hist[executionIndex]
        assert(len(histA) == len(histB))
        for threadIndex in histA:
            assert(len(histA[threadIndex]) == len(histB[threadIndex]))
            for registerIndex in histA[threadIndex]:
                assert(len(histA[threadIndex][registerIndex]) == len(histB[threadIndex][registerIndex]))
                for loadIndex in range(len(histA[threadIndex][registerIndex])):
                    if (histA[threadIndex][registerIndex][loadIndex] != histB[threadIndex][registerIndex][loadIndex]):
                        mismatchCountBase[executionIndex] += 1
                        if verbosity > 1:
                            print("Mismatch T%d R%d L%d base %X curr %X" % (threadIndex, registerIndex, loadIndex, histA[threadIndex][registerIndex][loadIndex], histB[threadIndex][registerIndex][loadIndex]))
    mismatchCountAll[baselineIndex] = mismatchCountBase

############################################################
## Reporting mismatch statistics
############################################################
if (args.print_stdout or args.gen_csv):
    ## 1. Colleting all information in one string
    # First line (note)
    outString = ",baselines\n"
    # Second line (baseline indices)
    outString += "execution"
    for baselineIndex in baselineList:
        outString += ",%d" % baselineIndex
    outString += ",total mismatch,best mismatch,best baseline\n"
    # Third+ line (mismatch count for executions, each execution in a line)
    for executionIndex in hist:
        outString += "%d" % executionIndex
        # individual mismatch counts
        totalMismatchCount = 0
        minMismatchCount = sys.maxint
        minMismatchBaselineIndex = -1
        for baselineIndex in baselineList:
            #print("baseline %d execution %d" % (baselineIndex, executionIndex))
            currMismatchCount = mismatchCountAll[baselineIndex][executionIndex]
            outString += ",%d" % currMismatchCount
            totalMismatchCount += currMismatchCount
            if currMismatchCount < minMismatchCount:
                minMismatchCount = currMismatchCount
                minMismatchBaselineIndex = baselineIndex
        # total mismatch counts for this execution across baseline
        outString += ",%d" % totalMismatchCount
        # minimum mismatch count, and its baseline index
        outString += ",%d,%d\n" % (minMismatchCount, minMismatchBaselineIndex)
    # Last line (total mismatch count for baselines, each baseline in a column)
    outString += "total"
    for baselineIndex in baselineList:
        totalMismatchCount = 0
        for executionIndex in hist:
            totalMismatchCount += mismatchCountAll[baselineIndex][executionIndex]
        outString += ",%d" % totalMismatchCount
    outString += "\n"

    ## 2. Priting out to stdout and csv file
    if args.print_stdout:
        print("\n### Mismatch count matrix")
        sys.stdout.write(outString)
    if args.gen_csv:
        diffFileName = "diff.csv"
        diffFP = open(diffFileName, "w")
        diffFP.write(outString)
        diffFP.close()
        print("### %s generated" % diffFileName)

############################################################
## k-medoids clustering (Partitioning Around Medoids (PAM) algorithm)
# NOTE: algorithm is adopted from
# https://en.wikibooks.org/wiki/Data_Mining_Algorithms_In_R/Clustering/Partitioning_Around_Medoids_(PAM)
# https://en.wikipedia.org/wiki/K-medoids
# NOTE: my implementation uses minimum dissimilarity to a medoid as a cost function
############################################################
if args.kmedoids:
    if (len(baselineList) != len(hist)):
        print("Warning: baseline executions are a subset of the entire executions...")
        print("# baseline executions %d vs. # entire executions %d" % (len(baselineList), len(hist)))
    else:
        ## Preprocessing (data structure)
        # 'mat' is a dissimilarity matrix between executions
        # For faster speed, data structure is re-created using 2-dimensional list, instead of dictionary
        execIdxs = sorted(baselineList)
        #print("unsorted baseline execution indices %s" % baselineList)
        #print("  sorted baseline execution indices %s" % execIdxs)
        mat = []
        for i in range(len(execIdxs)):
            matRow = []
            for j in range(len(execIdxs)):
                matRow.append(mismatchCountAll[execIdxs[i]][execIdxs[j]])
            mat.append(matRow)
        #print(mat)

        if (args.nummedoids <= 0):
            print("Error: nummedoids should be positive integer")
            sys.exit(1) 
        elif (len(execIdxs) < args.nummedoids):
            print("Warning: nummedoids is set to %d but only %d baseline executions exist" % (args.nummedoids, len(baselineList)))
        numMedoids = min(args.nummedoids, len(execIdxs))

        # Number of pairs (medoid and non-medoid) to be swapped
        numSwaps = numMedoids * (len(execIdxs) - numMedoids)
        numSwapTrials = int(round(numSwaps * args.percenttrials / float(100)))
        print("numSwaps %d numSwapTrials %d" % (numSwaps, numSwapTrials))

        random.seed(args.rand_seed)

        ## MAIN ALGORITHM
        # 1. Build phase
        # 1.1. Choose k medoid entities
        initMethod = 1  # This variable selects one of the initialization methods below
        if (initMethod == 0):    # 1st type: uniform random assignment
            medoids = random.sample(range(execIdxs), numMedoids)
        elif (initMethod == 1):  # 2nd type: equi-distance assignment
            medoids = []
            for i in range(0, numMedoids):
                if (numMedoids == 1):
                    percentile = 0.0
                else:
                    percentile = float(i) / (numMedoids - 1)
                index_float = (len(execIdxs) - 1) * percentile
                index_int = int(round(index_float))
                medoids.append(index_int)
            # sanity check (no duplicate)
            assert(len(list(set(medoids))) == numMedoids)
        elif (initMethod == 2):  # 3rd type: successive selection based on distances from others (original PAM method)
            # FIXME: implement here!
            # See page 7 of https://wis.kuleuven.be/stat/robust/papers/publications-1987/kaufmanrousseeuw-clusteringbymedoids-l1norm-1987.pdf
            print("Error: this intiialization method (%d) is not implemented" % (initMethod))
            sys.exit(1)
        else:
            print("Error: unrecognized initialization method (%d) for k-medoids clustering" % (initMethod))
            sys.exit(1)
        if (verbosity > 0):
            print("INFO: k-medoids clustering... initial medoids %s" % (medoids))

        nonmedoids = []
        for i in range(len(execIdxs)):
            if not i in medoids:
                nonmedoids.append(i)

        # 1.2. Assign every entity to its closest medoid
        cluster = [-1 for i in range(len(execIdxs))]
        totalCost = 0
        for i in range(len(execIdxs)):
            if i in medoids:
                cluster[i] = i
                totalCost += 0
            else:
                bestCost = sys.maxint
                bestCluster = -1
                for idx in medoids:
                    if (mat[i][idx] < bestCost):
                        bestCost = mat[i][idx]
                        bestCluster = idx
                cluster[i] = bestCluster
                totalCost += bestCost

        if (verbosity > 0):
            print("INFO: initial clustering cost %d, cluster %s" % (totalCost, cluster))

        # 2. Swap phase
        # 2.1. For each cluster search if any of the entities of the cluster
        # lower the average dissimilarity coefficient, if it does select the
        # entity that lowers this coefficient the most as the medoid for this
        # cluster.
        while True:
            changed = False
            trialCnt = 0
            trialHistory = set()
            while trialCnt < numSwapTrials:
                # Pick a pair of numbers to be swapped (one from medoid, another from non-medoid)
                # Uniform random... Monte-Carlo sampling (sampling with rejection)
                while True:
                    idxMedoid = random.randint(0, len(medoids)-1)
                    idxNonmedoid = random.randint(0, len(nonmedoids)-1)
                    execMedoid = medoids[idxMedoid]
                    execNonmedoid = nonmedoids[idxNonmedoid]
                    if not (execMedoid, execNonmedoid) in trialHistory:
                        break
                if (verbosity > 1):
                    print("INFO: medoid %d <-> non-medoid %d" % (execMedoid, execNonmedoid))
                trialCnt += 1
                trialHistory.add((execMedoid, execNonmedoid))

                # Create a new set of medoids and non-medoids
                # NOTE: Be careful not to forget manipulating medoids and nonmedoids later...
                medoids.append(execNonmedoid)
                medoids.remove(execMedoid)

                # Compute new cost and cluster assignment
                newCluster = [-1 for i in range(len(execIdxs))]
                newTotalCost = 0
                for i in range(len(execIdxs)):
                    if i in medoids:
                        newCluster[i] = i
                        newTotalCost += 0
                    else:
                        bestCost = sys.maxint
                        bestCluster = -1
                        for idx in medoids:
                            if (mat[i][idx] < bestCost):
                                bestCost = mat[i][idx]
                                bestCluster = idx
                        newCluster[i] = bestCluster
                        newTotalCost += bestCost

                if (newTotalCost < totalCost):
                    changed = True
                    cluster = newCluster
                    totalCost = newTotalCost
                    # Change nonmedoids accordingly (medoids was changed already)
                    nonmedoids.append(execMedoid)
                    nonmedoids.remove(execNonmedoid)
                    if (verbosity > 0):
                        print("INFO: successful swap (medoid %d <-> non-medoid %d)" % (execMedoid, execNonmedoid))
                else:
                    # Revert change in medoids
                    medoids.append(execMedoid)
                    medoids.remove(execNonmedoid)

            # 2.2. If at least one medoid has changed, then re-assign entities, else end the algorithm
            # Check if we should exit 'while True'
            if not changed:
                break

        # Print out resulting medroid
        print("### k-medoids clustering results")
        print("medoids: %s" % medoids)
        print("cluster: %s" % cluster)
        print("cost: %d" % totalCost)

