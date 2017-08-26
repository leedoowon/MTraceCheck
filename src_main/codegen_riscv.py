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

import sys
import math
import collections

#
# Register allocation
#
# t0: memory address / profile value (valid load value)
# t1: load target / store value
# t2: execution counter
# t3: signature increment
# t4: profiling signature (sum)
# t5: bss address (for storing results)
# t6: temporary (very short liveness ~ a couple of instructions)
# s0-s11:
# a0-a7:
# (x0-x4 are excluded here)
#


#
# RISC-V calling convention
#
# x0: zero
# x1: return address (ra)
# x2: stack pointer (sp)
# x3: global pointer (gp)
# x4: thread pointer (tp)
# x5-x7: temporaries (t0-t2)
# x8: saved register (s0) / frame pointer (fp)
# x9: saved register (s1)
# x10-x11: function arguments (a0-a1) / return values
# x12-x17: function arguments (a2-a7)
# x18-x27: saved register (s2-s11)
# x28-x31: temporaries (t3-t6)
#


def test_riscv(intermediate, textNamePrefix, textNameSuffix, headerName, dataBase, bssBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, fixedLoadReg, platform, profileName, numCores, strideType, verbosity):

    ####################################################################
    # Text section
    ####################################################################

    ####################################################################
    # See register allocation map above
    regAddr = "t0"
    if (fixedLoadReg):
        regLoad = "t1"
    else:
        regLoad = None
    regStore = "t1"
    regProfileValue = "t0"
    regSignature = "t4"
    regIncrement = "t3"
    regExecCount = "t2"  # This register should live across executions
    regCurrBssAddr = "t5"
    regTemp = "t6"
    regSync1 = "t4"
    regSync2 = "t3"
    regSync3 = "t0"
    regSync4 = "t1"
    regSync5 = "t5"
    ####################################################################

    if (profileName != None):
        profileFP = open(profileName, "w")
    else:
        profileFP = None

    threadIdx = 0
    for thread in intermediate:
        if (verbosity > 1):
            print("%s:%s(): Thread %d" % (__file__, sys._getframe().f_code.co_name, thread))  # NOTE: must be used with 'import sys'
        textName = textNamePrefix + str(thread) + textNameSuffix
        riscvList = []
        pathCount = 0  # Accumulated number of different value-sets
        profileCount = 0  # Accumulated number of profile statements
        signatureFlushCount = 0  # How many times the signature has been flushed to memory (i.e., number of words for each signature - 1)
        if (profileFP != None):
            profileFP.write("Thread %d Word %d\n" % (thread, signatureFlushCount))

        # Prologue code
        riscvList.append("## Start of generated code")
        riscvList.append("#include \"%s\"" % (headerName))
        riscvList.append("    .section .text")
        riscvList.append("    .globl thread%d_routine" % (thread))
        riscvList.append("    .globl thread%d_length" % (thread))
        riscvList.append("    .type thread%d_routine, @function" % (thread))  # FIXME: check @function
        riscvList.append("thread%d_routine:" % (thread))
        riscvList.append("## Prologue code")
        riscvList.append("t%d_prologue:" % (thread))
        if (platform == "baremetal"):
            riscvList.append("    # Waiting for start flag from test manager")
            riscvList.append("    la t0,thread_spawn_lock")
            riscvList.append("1:  lr.w t1,(t0)")
            riscvList.append("    addi t1,t1,1")
            riscvList.append("    sc.w t2,t1,(t0)")
            riscvList.append("    bnez t2,1b")
            riscvList.append("1:  la t0,thread_spawn_lock")
            riscvList.append("    lw t1,(t0)")
            riscvList.append("    li t2,NUM_THREADS")
            riscvList.append("    bne t1,t2,1b")
        riscvList.append("    li %s,0" % (regExecCount))

        # Main procedure
        riscvList.append("## Main code")
        riscvList.append("t%d_exec_loop:" % (thread))
        riscvList.append("#ifdef EXEC_SYNC")
        riscvList.append("    # Execution synchronization")
        riscvList.append("    #  %s: address of counter / counter pointer" % (regSync1))
        riscvList.append("    #  %s: counter pointer (indicating counter0 or counter1)" % (regSync2))
        riscvList.append("    #      When decrementing      | When busy-waiting")
        riscvList.append("    #  %s: previous counter value | up-to-date value" % (regSync3))
        riscvList.append("    #  %s: new counter value      | previous value" % (regSync4))
        riscvList.append("    la %s,thread_exec_barrier_ptr" % (regSync1))
        riscvList.append("    lw %s,0(%s)" % (regSync2,regSync1))
        riscvList.append("    beq %s,zero,2f" % (regSync2))
        riscvList.append("    la %s,thread_exec_barrier0" % (regSync1))
        riscvList.append("    j 1f")
        riscvList.append("2:  la %s,thread_exec_barrier1" % (regSync1))
        riscvList.append("")
        riscvList.append("    # Decrementing counter")
        riscvList.append("1:  lr.w %s,(%s)" % (regSync3,regSync1))
        riscvList.append("    addi %s,%s,1" % (regSync4,regSync3))
        riscvList.append("    sc.w %s,%s,(%s)" % (regSync3,regSync4,regSync1))
        riscvList.append("    bnez %s,1b" % (regSync3))
        riscvList.append("")
        riscvList.append("    # Check if it is last")
        riscvList.append("    li %s,NUM_THREADS" % (regSync3)) # only for comparison next line
        riscvList.append("    bne %s,%s,2f" % (regSync4,regSync3))
        riscvList.append("")
        riscvList.append("    ## (Fall through) Last thread")
        # regSync3: data location index
        # regSync4: data value
        # regSync5: address
        riscvList.append("    # Initialize test data section")
        riscvList.append("    li %s,0" % (regSync3))
        riscvList.append("1:  li %s,0xFFFF0000" % (regSync4))
        riscvList.append("    or %s,%s,%s" % (regSync4,regSync4,regSync3))
        riscvList.append("    li %s,TEST_DATA_SECTION" % (regSync5))
        if (strideType == 0):
            riscvList.append("    slli %s,%s,2  # NOTE: this must be manually changed to match with static address generation, strideType = 0" % (regTemp,regSync3))
        elif (strideType == 1):
            riscvList.append("    slli %s,%s,4  # NOTE: this must be manually changed to match with static address generation, strideType = 1" % (regTemp,regSync3))
        elif (strideType == 2):
            riscvList.append("    slli %s,%s,6  # NOTE: this must be manually changed to match with static address generation, strideType = 2" % (regTemp,regSync3))
        else:
            assert(False)
        riscvList.append("    add %s,%s,%s" % (regSync5,regSync5,regTemp))
        riscvList.append("    sw %s,0(%s)" % (regSync4,regSync5))
        riscvList.append("    addi %s,%s,1" % (regSync3,regSync3))
        riscvList.append("    li %s,NUM_SHARED_DATA" % (regSync4)) # only for comparison next line
        riscvList.append("    blt %s,%s,1b" % (regSync3,regSync4))
        riscvList.append("    # Modify pointer then initialize the old counter")
        riscvList.append("    # NOTE: Make sure to follow this order (pointer -> counter)")
        riscvList.append("    xori %s,%s,0x1" % (regSync2,regSync2))
        riscvList.append("    la %s,thread_exec_barrier_ptr" % (regSync1))
        riscvList.append("    sw %s,0(%s)" % (regSync2,regSync1))
        riscvList.append("    bne %s,zero,5f  # %s contains new pointer" % (regSync2,regSync2))
        riscvList.append("    la %s,thread_exec_barrier1" % (regSync1))
        riscvList.append("    j 4f")
        riscvList.append("5:  la %s,thread_exec_barrier0" % (regSync1))
        riscvList.append("4:  sw zero,0(%s)" % (regSync1))
        riscvList.append("    j 3f")
        riscvList.append("")
        riscvList.append("2:  ## Non-last thread")
        riscvList.append("    la %s,thread_exec_barrier_ptr" % (regSync1))
        riscvList.append("    lw %s,0(%s)  # %s indicates new pointer" % (regSync1,regSync1,regSync1))
        riscvList.append("    beq %s,%s,2b # %s indicates old pointer" % (regSync1,regSync2,regSync2))
        riscvList.append("")
        riscvList.append("3:  fence")
        riscvList.append("    # End of execution synchronization")
        riscvList.append("#endif")
        riscvList.append("    li %s,0" % (regSignature))
        for intermediateCode in intermediate[thread]:
            if (verbosity > 1):
                print("Code: %s" % (intermediateCode))
            riscvList.append("    # %s" % intermediateCode)
            if (intermediateCode["type"] == "ld"):
                # addr, reg
                if (strideType == 0):
                    absAddr = intermediateCode["addr"] * 4 + dataBase
                elif (strideType == 1):
                    absAddr = intermediateCode["addr"] * 16 + dataBase
                elif (strideType == 2):
                    absAddr = intermediateCode["addr"] * 64 + dataBase
                else:
                    assert(False)
                if (not fixedLoadReg):
                    regLoad = "r%d" % intermediateCode["reg"]
                # 1. construct effective address from immediate
                riscvList.append("    li %s,0x%X" % (regAddr, absAddr))
                # 2. load data from memory
                riscvList.append("    lw %s,0(%s)" % (regLoad, regAddr))
            elif (intermediateCode["type"] == "st"):
                # addr, value
                if (strideType == 0):
                    absAddr = intermediateCode["addr"] * 4 + dataBase
                elif (strideType == 1):
                    absAddr = intermediateCode["addr"] * 16 + dataBase
                elif (strideType == 2):
                    absAddr = intermediateCode["addr"] * 64 + dataBase
                else:
                    assert(False)
                # 1. construct effective address from immediate
                riscvList.append("    li %s,0x%X" % (regAddr, absAddr))
                # 2. value to be stored
                riscvList.append("    li %s,0x%X" % (regStore, intermediateCode["value"]))
                # 3. store data to memory
                riscvList.append("    sw %s,0(%s)" % (regStore, regAddr))
            elif (intermediateCode["type"] == "profile"):
                # reg, targets
                if (not fixedLoadReg):
                    regLoad = "r%d" % intermediateCode["reg"]
                riscvList.append("    # accumulated path count: %d" % pathCount)
                # 1. Flushing signature if overflow
                if ((pathCount * len(intermediateCode["targets"])) > ((1 << regBitWidth) - 1)):
                    riscvList.append("    # flushing current signature for overflow")
                    riscvList.append("    li %s,(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
                    riscvList.append("    addi %s,%s,%d" % (regCurrBssAddr, regCurrBssAddr, signatureFlushCount * regBitWidth / 8))
                    riscvList.append("    slli %s,%s,%d" % (regTemp, regExecCount, math.log(signatureSize, 2)))
                    riscvList.append("    add %s,%s,%s" % (regTemp, regTemp, regCurrBssAddr))
                    riscvList.append("    sw %s,(%s)" % (regSignature, regTemp))
                    riscvList.append("    li %s,0x0" % (regSignature))
                    pathCount = 0  # reset path count
                    signatureFlushCount += 1
                    if (profileFP != None):
                        profileFP.write("Thread %d Word %d\n" % (thread, signatureFlushCount))
                # 2. Computing increment
                if (profileFP != None):
                    weightTargetDict = collections.OrderedDict()
                targetIdx = 0
                for target in intermediateCode["targets"]:
                    if (pathCount == 0):
                        increment = targetIdx
                    else:
                        increment = pathCount * targetIdx
                    assert(increment < (1 << regBitWidth) - 1)
                    riscvList.append("    li %s,0x%X" % (regIncrement, increment))
                    riscvList.append("    li %s,0x%X" % (regProfileValue, target))
                    riscvList.append("    beq %s,%s,t%d_p%d_done" % (regLoad, regProfileValue, thread, profileCount))
                    if (profileFP != None):
                        weightTargetDict[increment] = target
                    targetIdx += 1
                riscvList.append("    j t%d_assert_invalid_value" % (thread))
                riscvList.append("t%d_p%d_done:" % (thread, profileCount))
                riscvList.append("    add %s,%s,%s" % (regSignature, regSignature, regIncrement))
                if (profileFP != None):
                    mapWeightTargetString = None
                    for weight in weightTargetDict:
                        if (mapWeightTargetString == None):
                            mapWeightTargetString = "0x%X:0x%X" % (weight, weightTargetDict[weight])
                        else:
                            mapWeightTargetString += "/0x%X:0x%X" % (weight, weightTargetDict[weight])
                    if (pathCount == 0):
                        profileFP.write("1,%d,%s\n" % (len(intermediateCode["targets"]), mapWeightTargetString))
                    else:
                        profileFP.write("%d,%d,%s\n" % (pathCount, len(intermediateCode["targets"]), mapWeightTargetString))
                if (pathCount == 0):
                    pathCount = len(intermediateCode["targets"])
                else:
                    pathCount = pathCount * len(intermediateCode["targets"])
                profileCount += 1
            else:
                print("Error: Unrecognized intermediate opcode %s" % (intermediateCode["type"]))
                sys.exit(1)
        riscvList.append("    li %s,(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
        riscvList.append("    addi %s,%s,%d" % (regCurrBssAddr, regCurrBssAddr, signatureFlushCount * regBitWidth / 8))
        riscvList.append("    slli %s,%s,%d" % (regTemp, regExecCount, math.log(signatureSize, 2)))
        riscvList.append("    add %s,%s,%s" % (regTemp, regTemp, regCurrBssAddr))
        riscvList.append("    sw %s,(%s)" % (regSignature, regTemp))
        # Fill zero for upper signature (assuming that BSS is not initialized to 0)
        for i in range((signatureFlushCount + 1) * regBitWidth / 8, signatureSize, regBitWidth / 8):
            riscvList.append("    addi %s,%s,%d" % (regCurrBssAddr, regCurrBssAddr, regBitWidth / 8))
            riscvList.append("    slli %s,%s,%d" % (regTemp, regExecCount, math.log(signatureSize, 2)))
            riscvList.append("    add %s,%s,%s" % (regTemp, regTemp, regCurrBssAddr))
            riscvList.append("    sw zero,(%s)" % (regTemp))
        riscvList.append("    addi %s,%s,1" % (regExecCount, regExecCount))
        riscvList.append("    li %s,%d" % (regTemp, numExecutions))
        riscvList.append("    blt %s,%s,t%d_exec_loop" % (regExecCount, regTemp, thread))
        # Epilogue code
        riscvList.append("## Epilogue code")
        riscvList.append("t%d_epilogue:" % (thread))
        riscvList.append("    j t%d_test_done" % (thread))
        riscvList.append("t%d_assert_invalid_value:" % (thread))
        riscvList.append("    j t%d_assert_invalid_value" % (thread))
        riscvList.append("t%d_test_done:" % (thread))
        if (platform == "linuxpthread"):
            riscvList.append("    ret")
        elif (platform == "baremetal"):
            riscvList.append("    la t0,thread_join_lock")
            riscvList.append("1:  lr.w t1,(t0)")
            riscvList.append("    addi t1,t1,1  # Immediate will be signextended")
            riscvList.append("    sc.w t2,t1,(t0)")
            riscvList.append("    bnez t2,1b")
            if (thread == 0):
                riscvList.append("    ret")
            else:
                riscvList.append("    j .  # halt")
        riscvList.append("thread%d_length: .word . - thread%d_routine + 0x20  # FIXME: 0x20 is added to copy constants possibly appended at the end of code" % (thread, thread))
        riscvList.append("## End of generated code")

        if (profileFP != None):
            for emptySignatureWordIdx in range(signatureFlushCount+1,signatureSize / (regBitWidth / 8)):
                profileFP.write("Thread %d Word %d\n" % (thread, emptySignatureWordIdx))

        # Assembly code writing
        asmFP = open(textName, "w")
        for asm in riscvList:
            asmFP.write("%s\n" % asm)
        asmFP.close()
        if (verbosity > 0):
            print("Assembly file %s generated" % textName)

        threadIdx += 1

    if (profileFP != None):
        profileFP.close()

def header_riscv(headerPath, threadList, dataBase, memLocs, bssBase, resultBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, platform, noPrint):
    headerString  = ""
    headerString += "/* Test configurations */\n"
    headerString += "#define EXEC_SYNC\n"
    if (noPrint):
        headerString += "#define NO_PRINT\n"
    else:
        headerString += "//#define NO_PRINT\n"
    headerString += "/* Test parameters */\n"
    headerString += "#define NUM_THREADS                 %d\n" % len(threadList)
    headerString += "#define EXECUTION_COUNT             %d\n" % numExecutions
    headerString += "#define NUM_SHARED_DATA             %d\n" % memLocs
    headerString += "#define SIGNATURE_SIZE_IN_BYTE      %d\n" % signatureSize
    headerString += "#define SIGNATURE_SIZE_IN_WORD      (%d/%d)\n" % (signatureSize, regBitWidth / 8)
    headerString += "/* Address map */\n"
    #if (platform == "baremetal"):
    #    headerString += "#define TEST_TEXT_SECTION           0x%X\n" % 0x44000000
    #    headerString += "#define TEST_THREAD_MAX_SIZE        0x100000\n"
    #    headerString += "#define TEST_THREAD_BASE(x)         (TEST_TEXT_SECTION + x * TEST_THREAD_MAX_SIZE)\n"
    headerString += "#define TEST_DATA_SECTION           0x%X\n" % dataBase
    headerString += "#define TEST_DATA_LOCATIONS         0x10000\n"
    headerString += "#define TEST_BSS_SECTION            0x%X\n" % bssBase
    headerString += "#define TEST_BSS_SIZE_PER_THREAD    0x%X\n" % bssSizePerThread
    if (platform == "baremetal"):
        headerString += "#define TEST_HASH_KEY_TABLE         0x%X\n" % 0x70000000
        headerString += "#define TEST_BSS_SECTION_END        (TEST_HASH_KEY_TABLE)\n"
        headerString += "#define TEST_HASH_VALUE_TABLE       0x%X\n" % 0x78000000

    headerFP = open(headerPath, "w")
    headerFP.write(headerString)
    headerFP.close()

def hash_riscv(filePath, headerFileName):
    hashString  = ""
    hashString += "/* FIXME: Bug warning when you compile with -O0 flag...\n"
    hashString += "   This code should be compiled with -O3 */\n"
    hashString += "#include \"%s\"\n" % headerFileName
    hashString += "#define NULL 0\n"
    hashString += "extern \"C\" void classify_result_binary();\n"
    hashString += "\n"
    hashString += "struct item\n"
    hashString += "{\n"
    hashString += "    unsigned long sig[NUM_THREADS * SIGNATURE_SIZE_IN_WORD];\n"
    hashString += "    unsigned int count;\n"
    hashString += "    struct item *left, *right;\n"
    hashString += "    int balance; /* -1, 0, or +1 */\n"
    hashString += "};\n"
    hashString += "\n"
    hashString += "int sigcmp (unsigned long *a, unsigned long *b)\n"
    hashString += "{\n"
    hashString += "    for (int i = 0; i < NUM_THREADS * SIGNATURE_SIZE_IN_WORD; i++) {\n"
    hashString += "        if (*a < *b)\n"
    hashString += "            return -1;\n"
    hashString += "        else if (*a > *b)\n"
    hashString += "            return 1;\n"
    hashString += "        else {\n"
    hashString += "            a++;\n"
    hashString += "            b++;\n"
    hashString += "        }\n"
    hashString += "    }\n"
    hashString += "    return 0;\n"
    hashString += "}\n"
    hashString += "\n"
    hashString += "struct item *new_item (unsigned long *sig_param)\n"
    hashString += "{\n"
    hashString += "    unsigned long *hash_size = (unsigned long *) hash_size_addr;\n"
    hashString += "    unsigned long address = TEST_HASH_KEY_TABLE + (*hash_size) * sizeof(struct item);\n"
    hashString += "    struct item *item_ptr = (struct item *) address;\n"
    hashString += "\n"
    hashString += "    for (int i = 0; i < NUM_THREADS * SIGNATURE_SIZE_IN_WORD; i++) {\n"
    hashString += "        //item_ptr->sig[i] = (sig_param != NULL) ? sig_param[i] : 0;\n"
    hashString += "        item_ptr->sig[i] = (sig_param != NULL) ? *(sig_param++) : 0;\n"
    hashString += "    }\n"
    hashString += "    item_ptr->count = (sig_param != NULL) ? 1 : 0;\n"
    hashString += "    item_ptr->left = NULL;\n"
    hashString += "    item_ptr->right = NULL;\n"
    hashString += "    item_ptr->balance = 0;\n"
    hashString += "    *hash_size = *hash_size + 1;\n"
    hashString += "    return item_ptr;\n"
    hashString += "}\n"
    hashString += "\n"
    hashString += "void binary_search_item (struct item *root, unsigned long *sig)\n"
    hashString += "{\n"
    hashString += "    /* Algorithm adopted from tsort.c */\n"
    hashString += "    struct item *p, *q, *r, *s, *t;\n"
    hashString += "    int a;\n"
    hashString += "\n"
    hashString += "    if (root->right == NULL) {\n"
    hashString += "        root->right = new_item (sig);\n"
    hashString += "        return;\n"
    hashString += "    }\n"
    hashString += "\n"
    hashString += "    t = root;\n"
    hashString += "    s = p = root->right;\n"
    hashString += "\n"
    hashString += "    while (true)\n"
    hashString += "    {\n"
    hashString += "        a = sigcmp (sig, p->sig);\n"
    hashString += "        if (a == 0) {\n"
    hashString += "            p->count++;\n"
    hashString += "            return;\n"
    hashString += "        }\n"
    hashString += "\n"
    hashString += "        if (a < 0)\n"
    hashString += "            q = p->left;\n"
    hashString += "        else\n"
    hashString += "            q = p->right;\n"
    hashString += "\n"
    hashString += "        if (q == NULL)\n"
    hashString += "        {\n"
    hashString += "            /* Add new element */\n"
    hashString += "            q = new_item (sig);\n"
    hashString += "\n"
    hashString += "            if (a < 0)\n"
    hashString += "                p->left = q;\n"
    hashString += "            else\n"
    hashString += "                p->right = q;\n"
    hashString += "\n"
    hashString += "            if (sigcmp (sig, s->sig) < 0)\n"
    hashString += "            {\n"
    hashString += "                r = p = s->left;\n"
    hashString += "                a = -1;\n"
    hashString += "            }\n"
    hashString += "            else\n"
    hashString += "            {\n"
    hashString += "                r = p = s->right;\n"
    hashString += "                a = 1;\n"
    hashString += "            }\n"
    hashString += "\n"
    hashString += "            while (p != q)\n"
    hashString += "            {\n"
    hashString += "                /* doowon: previously p->balance was 0 */\n"
    hashString += "                if (sigcmp (sig, p->sig) < 0)\n"
    hashString += "                {\n"
    hashString += "                    p->balance = -1;\n"
    hashString += "                    p = p->left;\n"
    hashString += "                }\n"
    hashString += "                else\n"
    hashString += "                {\n"
    hashString += "                    p->balance = 1;\n"
    hashString += "                    p = p->right;\n"
    hashString += "                }\n"
    hashString += "            }\n"
    hashString += "\n"
    hashString += "            /* Either tree was balanced or\n"
    hashString += "               adding new node makes the tree balanced */\n"
    hashString += "            if (s->balance == 0 || s->balance == -a)\n"
    hashString += "            {\n"
    hashString += "                s->balance += a;\n"
    hashString += "                return;\n"
    hashString += "            }\n"
    hashString += "\n"
    hashString += "            /* Reorganizing tree */\n"
    hashString += "            if (r->balance == a)\n"
    hashString += "            {\n"
    hashString += "                p = r;\n"
    hashString += "                if (a < 0)\n"
    hashString += "                {\n"
    hashString += "                    s->left = r->right;\n"
    hashString += "                    r->right = s;\n"
    hashString += "                }\n"
    hashString += "                else\n"
    hashString += "                {\n"
    hashString += "                    s->right = r->left;\n"
    hashString += "                    r->left = s;\n"
    hashString += "                }\n"
    hashString += "                s->balance = r->balance = 0;\n"
    hashString += "            }\n"
    hashString += "            else\n"
    hashString += "            {\n"
    hashString += "                /* doowon: I did not fully get this section of code */\n"
    hashString += "                if (a < 0)\n"
    hashString += "                {\n"
    hashString += "                    p = r->right;\n"
    hashString += "                    r->right = p->left;\n"
    hashString += "                    p->left = r;\n"
    hashString += "                    s->left = p->right;\n"
    hashString += "                    p->right = s;\n"
    hashString += "                }\n"
    hashString += "                else\n"
    hashString += "                {\n"
    hashString += "                    p = r->left;\n"
    hashString += "                    r->left = p->right;\n"
    hashString += "                    p->right = r;\n"
    hashString += "                    s->right = p->left;\n"
    hashString += "                    p->left = s;\n"
    hashString += "                }\n"
    hashString += "\n"
    hashString += "                s->balance = 0;\n"
    hashString += "                r->balance = 0;\n"
    hashString += "                if (p->balance == a)\n"
    hashString += "                    s->balance = -a;\n"
    hashString += "                else if (p->balance == -a)\n"
    hashString += "                    r->balance = a;\n"
    hashString += "                p->balance = 0;\n"
    hashString += "            }\n"
    hashString += "\n"
    hashString += "            if (s == t->right)\n"
    hashString += "                t->right = p;\n"
    hashString += "            else\n"
    hashString += "                t->left = p;\n"
    hashString += "\n"
    hashString += "            return;\n"
    hashString += "        }\n"
    hashString += "\n"
    hashString += "        /* Find the closest imbalanced node */\n"
    hashString += "        if (q->balance)\n"
    hashString += "        {\n"
    hashString += "            t = p;\n"
    hashString += "            s = q;\n"
    hashString += "        }\n"
    hashString += "\n"
    hashString += "        /* Iterate to next level */\n"
    hashString += "        p = q;\n"
    hashString += "    }\n"
    hashString += "}\n"
    hashString += "\n"
    hashString += "void classify_result_binary()\n"
    hashString += "{\n"
    hashString += "    unsigned long *curr_key = (unsigned long *) curr_key_addr;  // [number of threads] * [number of word for signature per thread]\n"
    hashString += "    unsigned long *result = (unsigned long *) result_addr;\n"
    hashString += "    unsigned long *hash_size_ptr = (unsigned long *) hash_size_addr;\n"
    hashString += "    struct item *root;\n"
    hashString += "\n"
    hashString += "    *hash_size_ptr = 0;\n"
    hashString += "    root = new_item(NULL);\n"
    hashString += "\n"
    hashString += "    /* Hash function */\n"
    hashString += "    for (int i = 0; i < EXECUTION_COUNT; i++) {\n"
    hashString += "        unsigned long bss_addr, hash_key_addr, hash_value_addr;  // NOTE: This is not pointer-typed\n"
    hashString += "\n"
    hashString += "        // 1. Collect signatures (\"current key\") from all threads\n"
    hashString += "        for (int t = 0; t < NUM_THREADS; t++) {\n"
    hashString += "            bss_addr = TEST_BSS_SECTION + t * TEST_BSS_SIZE_PER_THREAD + i * SIGNATURE_SIZE_IN_WORD * sizeof(unsigned long);\n"
    hashString += "            for (int w = 0; w < SIGNATURE_SIZE_IN_WORD; w++) {\n"
    hashString += "                curr_key[t*SIGNATURE_SIZE_IN_WORD+w] = *(unsigned long *) bss_addr;\n"
    hashString += "                bss_addr += sizeof(unsigned long);\n"
    hashString += "            }\n"
    hashString += "        }\n"
    hashString += "\n"
    hashString += "        // 2. Binary-search keys in the hash table if it is equal to current key\n"
    hashString += "        //    If not found, add current key into hash table (with value 1)\n"
    hashString += "        binary_search_item (root, curr_key);\n"
    hashString += "        // hash_size is increased in this function\n"
    hashString += "    }\n"
    hashString += "\n"
    hashString += "    // Verify sum of hash values\n"
    hashString += "    unsigned long sumHashValue = 0;\n"
    hashString += "    unsigned long hash_size = *hash_size_ptr;\n"
    hashString += "    for (int h = 0; h < hash_size; h++) {\n"
    hashString += "        unsigned long address = TEST_HASH_KEY_TABLE + h * sizeof(struct item);\n"
    hashString += "        struct item *item_ptr = (struct item *) address;\n"
    hashString += "        sumHashValue += item_ptr->count;\n"
    hashString += "    }\n"
    hashString += "\n"
    hashString += "    result[2] = (hash_size - 1);\n"
    hashString += "    result[3] = sumHashValue;\n"
    hashString += "}\n"

    hashFileFP = open(filePath, "w")
    hashFileFP.write(hashString)
    hashFileFP.close()

def manager_riscv(managerFileName, headerName, threadList, signatureSize, regBitWidth, numCores, strideType):
    managerString  = ""
    managerString += "/* Source code adopted from torture test generator in rocket-chip.\n"
    managerString += "   See LICENSE Unversity of California as follows\n"
    managerString += "\n"
    managerString += "Copyright (c) 2012-2015, The Regents of the University of California (Regents).\n"
    managerString += "All Rights Reserved.\n"
    managerString += "\n"
    managerString += "Redistribution and use in source and binary forms, with or without\n"
    managerString += "modification, are permitted provided that the following conditions are met:\n"
    managerString += "1. Redistributions of source code must retain the above copyright\n"
    managerString += "   notice, this list of conditions and the following disclaimer.\n"
    managerString += "2. Redistributions in binary form must reproduce the above copyright\n"
    managerString += "   notice, this list of conditions and the following disclaimer in the\n"
    managerString += "   documentation and/or other materials provided with the distribution.\n"
    managerString += "3. Neither the name of the Regents nor the\n"
    managerString += "   names of its contributors may be used to endorse or promote products\n"
    managerString += "   derived from this software without specific prior written permission.\n"
    managerString += "\n"
    managerString += "IN NO EVENT SHALL REGENTS BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,\n"
    managerString += "SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING\n"
    managerString += "OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF REGENTS HAS\n"
    managerString += "BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.\n"
    managerString += "\n"
    managerString += "REGENTS SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED TO,\n"
    managerString += "THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR\n"
    managerString += "PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, PROVIDED\n"
    managerString += "HEREUNDER IS PROVIDED \"AS IS\". REGENTS HAS NO OBLIGATION TO PROVIDE\n"
    managerString += "MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS. */\n"
    managerString += "\n"
    managerString += "#include \"encoding.h\"\n"
    managerString += "#include \"%s\"\n" % headerName
    managerString += "#define TESTNUM x28  // from riscv_test.h in torture test generator\n"
    managerString += "\n"
    managerString += "    .globl classify_result_binary\n"
    managerString += "\n"
    managerString += "    .section .text.init\n"
    managerString += "    .align  6\n"
    managerString += "    .weak stvec_handler\n"
    managerString += "    .weak mtvec_handler\n"
    managerString += "    .globl _start\n"
    managerString += "_start:\n"
    managerString += "    /* reset vector */\n"
    managerString += "    j reset_vector\n"
    managerString += "    .align 2\n"
    managerString += "trap_vector:\n"
    managerString += "    /* test whether the test came from pass/fail */\n"
    managerString += "    csrr t5, mcause\n"
    managerString += "    li t6, CAUSE_USER_ECALL\n"
    managerString += "    beq t5, t6, write_tohost\n"
    managerString += "    li t6, CAUSE_SUPERVISOR_ECALL\n"
    managerString += "    beq t5, t6, write_tohost\n"
    managerString += "    li t6, CAUSE_MACHINE_ECALL\n"
    managerString += "    beq t5, t6, write_tohost\n"
    managerString += "    /* if an mtvec_handler is defined, jump to it */\n"
    managerString += "    la t5, mtvec_handler\n"
    managerString += "    beqz t5, 1f\n"
    managerString += "    jr t5\n"
    managerString += "    /* was it an interrupt or an exception? */\n"
    managerString += "1:  csrr t5, mcause\n"
    managerString += "    bgez t5, handle_exception\n"
    managerString += "    j other_exception /* No interrupts should occur */\n"
    managerString += "handle_exception:\n"
    managerString += "    /* we don't know how to handle whatever the exception was */\n"
    managerString += "other_exception:\n"
    managerString += "    /* some unhandlable exception occurred */\n"
    managerString += "1:  ori TESTNUM, TESTNUM, 1337\n"
    managerString += "write_tohost:\n"
    managerString += "    sw TESTNUM, tohost, t5\n"
    managerString += "    j write_tohost\n"
    managerString += "reset_vector:\n"
    managerString += "    li TESTNUM, 0\n"
    managerString += "    la t0, trap_vector\n"
    managerString += "    csrw mtvec, t0\n"
    managerString += "    csrwi medeleg, 0\n"
    managerString += "    csrwi mideleg, 0\n"
    managerString += "    csrwi mie, 0\n"
    managerString += "    /* if an stvec_handler is defined, delegate exceptions to it */\n"
    managerString += "    la t0, stvec_handler\n"
    managerString += "    beqz t0, 1f\n"
    managerString += "    csrw stvec, t0\n"
    managerString += "    li t0, (1 << CAUSE_FAULT_LOAD) | \\\n"
    managerString += "           (1 << CAUSE_FAULT_STORE) | \\\n"
    managerString += "           (1 << CAUSE_FAULT_FETCH) | \\\n"
    managerString += "           (1 << CAUSE_MISALIGNED_FETCH) | \\\n"
    managerString += "           (1 << CAUSE_USER_ECALL) | \\\n"
    managerString += "           (1 << CAUSE_BREAKPOINT)\n"
    managerString += "    csrw medeleg, t0\n"
    managerString += "    csrr t1, medeleg\n"
    managerString += "    bne t0, t1, other_exception\n"
    managerString += "1:  csrwi mstatus, 0\n"
    managerString += "    la t0, 1f\n"
    managerString += "    csrw mepc, t0\n"
    managerString += "    csrr a0, mhartid\n"
    managerString += "    mret\n"  # FIXME: uncomment it
    managerString += "1:  j test_start  // a0: mhartid\n"
    managerString += "\n"
    managerString += "    .section .text\n"
    managerString += "test_start:\n"
    for thread in range(numCores):
        managerString += "    la t0, thread%d_routine\n" % thread
        if (thread != numCores - 1):
            managerString += "    li t1, %d\n" % thread
            managerString += "    beq a0, t1, 1f\n"  # FIXME: a0 -> t0
    managerString += "1:  jalr t0\n"
    managerString += "\n"
    managerString += "wait_for_test_threads:\n"
    managerString += "    /* NOTE: Only one thread reaches here... others are looping in test routine */\n"
    managerString += "    lw t5, thread_join_lock\n"
    managerString += "    li t6, NUM_THREADS\n"
    managerString += "    bne t5, t6, wait_for_test_threads\n"
    managerString += "    /* End of test routine */\n"
    managerString += "\n"
    managerString += "    /* TODO: Classify results */\n"
    managerString += "\n"
    managerString += "    j test_end\n"
    managerString += "\n"
    managerString += "test_end:\n"
    managerString += "    fence\n"
    managerString += "    li TESTNUM, 1;\n"
    managerString += "    ecall\n"
    managerString += "    unimp\n"
    managerString += "\n"
    managerString += "    /* Data section */\n"
    managerString += "    .section .data\n"
    managerString += "    .align 8\n"
    managerString += "    .globl thread_spawn_lock, thread_join_lock, thread_exec_barrier0, thread_exec_barrier1, thread_exec_barrier_ptr\n"
    managerString += "thread_spawn_lock: .word 0x0\n"
    managerString += "thread_join_lock:  .word 0x0  // incremented when spawning thread, decremented when thread is done\n"
    managerString += ".align 6; thread_exec_barrier0:    .word 0x0\n"
    managerString += ".align 6; thread_exec_barrier1:    .word 0x0\n"
    managerString += ".align 6; thread_exec_barrier_ptr: .word 0x0\n"
    managerString += "\n"
    managerString += "    .pushsection .tohost,\"aw\",@progbits\n"
    managerString += ".align 6; .globl tohost;   tohost:   .dword 0\n"
    managerString += ".align 6; .globl fromhost; fromhost: .dword 0\n"
    managerString += "    .popsection\n"

    managerFP = open(managerFileName, "w")
    managerFP.write(managerString)
    managerFP.close()

