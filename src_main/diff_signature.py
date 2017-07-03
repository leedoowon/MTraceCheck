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
import parse_weight

""" Log format for signatures
       0: 0x0000000000b4d3fa 0x000000000b839f08
       1: 0x0000000000b4d437 0x000000000b95ddff
       2: 0x0000000000b51f37 0x00000000045f81b7
       3: 0x0000000000b4d437 0x000000000b95ddd7
       4: 0x0000000000b4d437 0x000000000b964ef7
       5: 0x0000000000c91437 0x000000000b8e9d97
       6: 0x0000000000b4d437 0x000000000b95ddd7
       7: 0x0000000000b51c37 0x00000000045f81b7
       8: 0x0000000000b4d437 0x000000000b95ddd7
       9: 0x0000000000b4d437 0x0000000004609af7
      10: 0x0000000000c91737 0x000000000b8e9dbf
                      ...
  131070: 0x0000000000c91437 0x000000000b95ddd7
  131071: 0x0000000000b4d437 0x000000000b964ef7
 0x0000000000b4d3fa 0x000000000b839f08: 1
 0x0000000000b4d437 0x000000000317037f: 1
 0x0000000000b4d437 0x00000000031703f7: 31
                      ...
 0x0000000000ca3437 0x000000000b8e9e0f: 1
 0x0000000000ca3437 0x000000000b8e9e37: 1
 0x0000000000ca3437 0x000000000b948c7f: 1
 0x0000000000ca3437 0x000000000b94c497: 1
 0x0000000000ca3437 0x000000000b953517: 3
 0x0000000000ca3437 0x000000000b95ddd7: 2606
 0x0000000000ca3437 0x000000000b964e57: 81
 0x0000000000ca35b7 0x000000000b8df4d7: 2
Number of unique results 351 out of 131072
"""

""" Weights for parsing signatures (no indentation in real code)
Thread 0 Word 0
    Profile 0
    Profile 1
    ...
Thread 0 Word 1
  ...
Thread 1 Word 0
  ...
Thread 2 Word 0
  ...

For each profile element: "weight stride, # weights" (e.g., 4,5 => weights are 0, 4, 8, 12, 16)
"""

parser = argparse.ArgumentParser(description="Arguments for %s " % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--signature-file", default=None)
parser.add_argument("--profile-file", default=None)
args = parser.parse_args()
assert(args.signature_file != None and args.profile_file != None)

verbosity = args.verbose

########################################################################
# Read ordered signature words
########################################################################
signatureFP = open(args.signature_file, "r")
signatureList = []
for line in signatureFP:
    if not line.startswith(" 0x"):
        continue
    tokens = line.split(":")
    signatureStrings = tokens[0].lstrip().split()
    signatures = []
    for string in signatureStrings:
        signatures.append(int(string, 16))
    signatureList.append(signatures)
signatureFP.close()

# Verify if the signatureList is fully ordered in ascending order
fullyOrdered = True
prevSignature = signatureList[0]
signatureLength = len(signatureList[0])
for signatureIdx in range(1,len(signatureList)):
    signature = signatureList[signatureIdx]
    assert(len(signature) == signatureLength)
    for wordIdx in range(signatureLength):
        if signature[wordIdx] > prevSignature[wordIdx]:
            break
        elif signature[wordIdx] < prevSignature[wordIdx]:
            print("Warning: prevSignature %s currSignature %s" % (prevSignature, signature))
            fullyOrdered = False
    prevSignature = signature
if (fullyOrdered):
    print("Info: signatures are fully ordered")
else:
    print("Info: signatrues are NOT ordered fully")

if (verbosity > 0):
    for signature in signatureList:
        for perThreadSignature in signature:
            sys.stdout.write(" 0x%X" % perThreadSignature)
        sys.stdout.write("\n")

########################################################################
# Read signature weights
########################################################################
returnDict = parse_weight.parseWeights(args.profile_file)
weightList = returnDict['weightList']
numThreads = returnDict['numThreads']
numWordsPerThread = returnDict['numWordsPerThread']

if (verbosity > 0):
    for weightWord in weightList:
        print(weightWord)

# Reordering weights
# NOTE: THIS SHOULD BE CAREFULLY UNCOMMENTED IN CONJUNCTION WITH OTHER FILES (codegen_common.py, ANALYSIS TOOLS)
"""
assert(len(weightList) == numThreads * numWordsPerThread)
newWeightList = [[] for i in range(numThreads * numWordsPerThread)]
for t in range(numThreads):
    for w in range(numWordsPerThread):
        idx = numThreads * (numWordsPerThread - 1 - w) + t
        newWeightList[idx] = weightList[t * numWordsPerThread + w]
weightList = newWeightList

if (verbosity > 0):
    for weightWord in weightList:
        print(weightWord)
"""

########################################################################
# Compute differences between two adjacent signatures
########################################################################
differenceList = []
numDiffLoadsList = []
if len(signatureList) > 1:
    signatureLength = len(signatureList[0])
    assert(len(weightList) == signatureLength)
    for signatureIdx in range(1, len(signatureList)):
        difference = []
        for wordIdx in range(signatureLength):
            difference.append(signatureList[signatureIdx][wordIdx] - signatureList[signatureIdx-1][wordIdx])
        differenceList.append(difference)
    for difference in differenceList:
        numDiffLoads = 0
        for wordIdx in range(signatureLength):
            num = 0
            currDiff = abs(difference[wordIdx])
            for weightTuple in reversed(weightList[wordIdx]):
                if (currDiff == 0):
                    break
                weight = weightTuple[0]
                possibilities = weightTuple[1]
                #print("currDiff %d weight %d possibilities %d" % (currDiff, weight, possibilities))
                if currDiff >= weight:
                    pathIdx = currDiff / weight
                    assert(pathIdx < possibilities)
                    currDiff -= pathIdx * weight
                    num += 1
            assert(currDiff == 0)
            numDiffLoads += num
        numDiffLoadsList.append(numDiffLoads)
else:
    print("Info: only 1 signature found")

if (verbosity > 0):
    assert(len(differenceList) == len(numDiffLoadsList))
    for idx in range(len(differenceList)):
        print("%s - %s" % (differenceList[idx], numDiffLoadsList[idx]))

sumDiffLoads = 0
for idx in range(len(numDiffLoadsList)):
    sumDiffLoads += numDiffLoadsList[idx]
print("Info: %d different loads from last graph" % sumDiffLoads)
