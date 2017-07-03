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
import instruction

def parseProgram(program_file, wo_file, ignoreReg, verbosity):
    progFP = open(program_file, "r")
    prog = dict()
    intra = dict()
    for instStr in progFP:
        # NOTE: See intermediate file example in gen_mtrand.py
        tokens = instStr.split("#")
        assert(len(tokens) >= 2)
        thread = int(tokens[0].split("/")[0])
        inst = int(tokens[0].split("/")[1])
        asm = tokens[1].rstrip() # rstrip() for removing \n when no instIntraDeps exist
        instIntraDeps = []
        for intraDepIndex in range(2,len(tokens)):
            instIntraDeps.append(int(tokens[intraDepIndex]))

        if (not thread in prog):
            prog[thread] = dict()
            intra[thread] = dict()
        assert(not inst in prog[thread])
        assert(not inst in intra[thread])
        prog[thread][inst] = asm
        intra[thread][inst] = instIntraDeps
    progFP.close()

    # Write-order parsing should be followed by program parsing, not the other way around
    writeOrder = dict()
    for thread in prog:
        writeOrder[thread] = dict()
    if (wo_file != None):
        woFP = open(wo_file, "r")
        for woLine in woFP:
            tokens = woLine.split("#")
            assert(len(tokens) >= 2)
            thread = int(tokens[0].split("/")[0])
            address = int(tokens[0].split("/")[1], 16)
            writeOrderAddress = []
            for storeInstIndex in range(1,len(tokens)):
                writeOrderAddress.append(int(tokens[storeInstIndex]))

            assert(thread in writeOrder)
            assert(not address in writeOrder[thread])
            writeOrder[thread][address] = writeOrderAddress
        woFP.close()

    # Construct a lookup table to find instruction index from load value
    # lookupInstFromLoad[thread][register index] = a list of instructions whose load values are stored in this register
    lookupInstFromLoad = dict()
    storeTable = dict()
    for thread in prog:
        lookupInstFromLoad[thread] = dict()
        lastInst = -1
        for inst in prog[thread]:
            # assume that "inst" is increasing monotonically... if it is not the case, stop
            if inst <= lastInst:
                print("Error: inst variable should monotonically increase when assigning load value to instruction index")
                sys.exit(1)
            lastInst = inst
            asm = prog[thread][inst]
            # Assembly code examples
            #   ld 0x0,r14
            #   st 0x2
            tokens = asm.split(",")  # e.g., ["ld 0x0", "r14"] or ["st 0x2"]
            if (tokens[0].startswith("ld")):
                assert(len(tokens) > 1)
                registerString = tokens[1]
                assert(registerString[0] == "r")
                if (ignoreReg):
                    registerIndex = 0 
                else:
                    registerIndex = int(registerString[1:])
                if not registerIndex in lookupInstFromLoad[thread]:
                    lookupInstFromLoad[thread][registerIndex] = []
                lookupInstFromLoad[thread][registerIndex].append(inst)
            if (tokens[0].startswith("st")):
                addressString = tokens[0].split(" ")[1]
                addressInt = int(addressString, 16)
                if not addressInt in storeTable:
                    storeTable[addressInt] = []
                storeTable[addressInt].append(instruction.getMemOp(thread, inst))

    if verbosity:
        print("### Intermediate file contents loaded in %s" % __file__)
        for thread in prog:
            print("Therad %d" % thread)
            print("Instructions")
            for inst in prog[thread]:
                print("%d: %s deps %s" % (inst, prog[thread][inst], intra[thread][inst]))
            print("Load registers")
            for registerIndex in lookupInstFromLoad[thread]:
                print("%d: %s" % (registerIndex, lookupInstFromLoad[thread][registerIndex]))
            print("Write order")
            for address in writeOrder[thread]:
                print("Address 0x%X: %s" % (address, writeOrder[thread][address]))

    return {"progInfo": prog, "intraDep": intra, "writeOrder": writeOrder, "lookupTable": lookupInstFromLoad, "storeTable": storeTable}
