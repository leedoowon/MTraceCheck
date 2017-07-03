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
import parse_intermediate
import parse_weight
import collections

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--intermediate", default="test.txt")
parser.add_argument("--profile-file", default="profile.txt")
parser.add_argument("--output", "-o", default="hist_decoded.txt")
parser.add_argument("signature_file", metavar="log file of signatures", help="a file that includes signatures to be processed")
args = parser.parse_args()

verbosity = args.verbose

def parseSignatures(signatureFile):
    numWords = None
    listSignatures = []
    signatureFP = open(signatureFile, "r")
    for line in signatureFP:
        # Example: 0x0000000000c91437 0x000000000b8e9e0f: 60
        #          (signatures from all threads: how many times this occurred)
        if not line.startswith(" 0x"):
            continue
        if (verbosity > 1):
            print(line.rstrip())
        tokens = line.split(":")
        if (len(tokens) < 2):
            print("Warning: Line %s ignored in %s" % (line, __file__))
            continue
        frequency = int(tokens[1])
        signatureTokens = tokens[0].lstrip().rstrip().split(" ")
        if (numWords == None):
            numWords = len(signatureTokens)
        else:
            assert(len(signatureTokens) == numWords)
        currentSignature = []
        for perThreadSignature in signatureTokens:
            currentSignature.append(int(perThreadSignature, 16))
        listSignatures.append(currentSignature)
    signatureFP.close()
    return listSignatures

def decodeSignatureElements(intermediate):
    # FIXME: This code is outdated and does not properly handle multi-word signatures
    assert(False)
    maps = dict()
    regs = dict()
    for thread in intermediate:
        pathCount = 0  # Accumulated number of different value-sets
        signatureElements = []
        signatureRegOrder = []
        for intermediateCode in intermediate[thread]:
            if (intermediateCode["type"] == "profile"):
                # NOTE: Following code has been copied from codegen_x86(arm).py
                # FIXME: Refactor code
                if (pathCount == 0):
                    newPathCount = len(intermediateCode["targets"])
                else:
                    newPathCount = pathCount * len(intermediateCode["targets"])
                if (newPathCount < pathCount):
                    print("Error: Overflow...")
                    sys.exit(1)
                currSignatureDict = collections.OrderedDict()
                targetIdx = 0
                for target in intermediateCode["targets"]:
                    if (pathCount == 0):
                        currSignature = targetIdx
                    else:
                        currSignature = pathCount * targetIdx
                    assert(currSignature < 0xFFFFFFFFFFFFFFFF)  # FIXME: support larger increment
                    assert(not currSignature in currSignatureDict)
                    currSignatureDict[currSignature] = target
                    targetIdx += 1
                signatureElements.append(currSignatureDict)
                signatureRegOrder.append(intermediateCode["reg"])
                pathCount = newPathCount
            else:
                # ignore other statements (e.g., ld, st)
                pass
        assert(not thread in maps)
        maps[thread] = signatureElements
        regs[thread] = signatureRegOrder
        if (verbosity > 0):
            print("Thread %d" % thread)
            for idx in range(len(maps[thread])):
                eachSignatureElement = maps[thread][idx]
                sys.stdout.write("%2d-" % signatureRegOrder[idx])
                for eachSignatureKey in eachSignatureElement:
                    sys.stdout.write("  %X: %X" % (eachSignatureKey, eachSignatureElement[eachSignatureKey]))
                sys.stdout.write("\n")
    return {"signatures": maps, "regOrder": regs}

def reconstructHistory(maps, regs, listSignatures, numThreads, numWordsPerThread, outputFile, debug):
    outputFP = open(outputFile, "w")
    signatureCount = 0
    for signatureSet in listSignatures:
        executionStr = "### Execution %d\n" % signatureCount

        if (debug):
            print("Signature: %s" % signatureSet)

        for threadIdx in range(numThreads):
            hist = dict()
            for wordIdx in reversed(range(numWordsPerThread)):
                if (debug):
                    print("Thread %d Word %d" % (threadIdx, wordIdx))
                # NOTE: descending wordIdx because the signature is decoded backward
                signatureWordIdx = threadIdx * numWordsPerThread + wordIdx
                signature = signatureSet[signatureWordIdx]
                remainingSignature = signature
                profileIdx = len(maps[signatureWordIdx]) - 1  # Decending order
                while profileIdx >= 0:
                    if (regs == None):
                        reg = 0
                    else:
                        # NOTE: This register-indexing might be outdated
                        reg = regs[signatureWordIdx][profileIdx]
                    if (not reg in hist):
                        hist[reg] = []
                    descendingWeights = list(reversed(maps[signatureWordIdx][profileIdx].keys()))
                    #print(orderedDict)
                    weightFound = False
                    for weightToCompare in descendingWeights:
                        if remainingSignature >= weightToCompare:
                            hist[reg].insert(0, maps[signatureWordIdx][profileIdx][weightToCompare])
                            remainingSignature -= weightToCompare
                            weightFound = True
                            break
                    assert(weightFound)
                    profileIdx -= 1
                assert(remainingSignature == 0)
            executionStr += "T%d:" % (threadIdx)
            for reg in sorted(hist.keys()):
                executionStr += " %d-" % reg
                for valueIdx in range(len(hist[reg])):
                    if (valueIdx > 0):
                        executionStr += ","
                    executionStr += "%X" % hist[reg][valueIdx]
            executionStr += "\n"
        outputFP.write(executionStr)
        #sys.stdout.write(executionStr)
        signatureCount += 1
    outputFP.close()

if __name__ == "__main__":
    listSignatures = parseSignatures(args.signature_file)

    if (args.debug):
        signatureIndex = 0
        for signatureSet in listSignatures:
            sys.stdout.write("%d:" % signatureIndex)
            for eachSignature in signatureSet:
                sys.stdout.write(" 0x%X" % eachSignature)
            sys.stdout.write("\n")
            signatureIndex += 1

    # NOTE: These below code is obsolete (old-style history)
    #returnDict = parse_intermediate.parseIntermediate(args.intermediate, verbosity)
    #header = returnDict["header"]
    #intermediate = returnDict["intermediate"]
    #returnDict = decodeSignatureElements(intermediate)
    #maps = returnDict["signatures"]
    #regs = returnDict["regOrder"]
    #reconstructHistory(maps, regs, listSignatures, args.output)
    # PREVIOUS DECLARATION: def reconstructHistory(maps, regs, listSignatures, outputFile):

    returnDict = parse_weight.parseWeights(args.profile_file)
    weightList = returnDict['weightList']
    numThreads = returnDict['numThreads']
    numWordsPerThread = returnDict['numWordsPerThread']

    if (args.debug > 0):
        print(weightList)
        print(numThreads)
        print(numWordsPerThread)

    assert(len(weightList) == numThreads * numWordsPerThread)

    # Construct map from weightList
    maps = []
    for signatureWordIdx in range(numThreads * numWordsPerThread):
        profileLen = len(weightList[signatureWordIdx])
        mapSignatureWord = []
        for profileIdx in range(len(weightList[signatureWordIdx])):
            mapWeightTarget = collections.OrderedDict()
            weightTargetPairs = weightList[signatureWordIdx][profileIdx][2].split("/")
            for weightTargetPair in weightTargetPairs:
                tokens = weightTargetPair.split(":")
                assert(len(tokens) == 2)
                weight = int(tokens[0], 16)
                target = int(tokens[1], 16)
                mapWeightTarget[weight] = target
            mapSignatureWord.append(mapWeightTarget)
        maps.append(mapSignatureWord)

    reconstructHistory(maps, None, listSignatures, numThreads, numWordsPerThread, args.output, args.debug)

    if (verbosity > 0):
        print("%s created" % args.output)

