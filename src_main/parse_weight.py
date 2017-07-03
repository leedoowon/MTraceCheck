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

def parseWeights(weightFile):
    weightFP = open(weightFile, "r")
    weightList = []
    weightWord = []
    firstNonDigitLine = True
    maxThreadIdx = None
    maxWordIdx = None
    for line in weightFP:
        if line[0].isdigit():
            tokens = line.lstrip().rstrip().split(',')
            assert(len(tokens) >= 2)
            weightWord.append([int(tokens[0]),int(tokens[1]),tokens[2]])
        else:
            tokens = line.split()
            assert(tokens[0] == "Thread" and tokens[2] == "Word")
            if (maxThreadIdx == None or maxThreadIdx < int(tokens[1])):
                maxThreadIdx = int(tokens[1])
            if (maxWordIdx == None or maxWordIdx < int(tokens[3])):
                maxWordIdx = int(tokens[3])
            if (not firstNonDigitLine):
                weightList.append(weightWord)
            firstNonDigitLine = False
            weightWord = []
    weightList.append(weightWord)
    weightFP.close()
    return {'weightList':weightList, 'numThreads':maxThreadIdx+1, 'numWordsPerThread':maxWordIdx+1}

