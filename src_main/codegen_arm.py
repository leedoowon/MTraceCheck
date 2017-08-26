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
# r0 : memory address / profile value (valid load value)
# r1 : load target / store value
# r2 : execution counter
# r3 : signature increment
# r4 : profiling signature (sum)
# r5 :
# r6 :
# r7 :
# r8 :
# r9 :
# r10:
# r11:
# r12: bss address (for storing results)
# r13: (SP)
# r14: (LR)
# r15: (PC)
#


#
# ARM calling convention (http://wiki.osdev.org/ARM_Overview)
#
# return value: r0, r1
# parameter registers: r0, r1, r2, r3
# additional parameters: stack (r13) ** 8-byte stack alignment **
# scratch registers: r0, r1, r2, r3, r12
# preserved registers: r4, r5, r6, r7, r8, r9, r10, r11, r13
# return address: r14
#


def high16(data):
    return (data >> 16) & 0xFFFF

def low16(data):
    return data & 0xFFFF

# NOTE: r4 might need to be preserved before starting executing generated code

def test_arm(intermediate, textNamePrefix, textNameSuffix, headerName, dataBase, bssBase, bssSizePerThread, stackPointer, signatureSize, regBitWidth, numExecutions, fixedLoadReg, platform, profileName, numCores, strideType, verbosity):

    ####################################################################
    # Text section
    ####################################################################

    ####################################################################
    # See register allocation map above
    regAddr = "r0"
    if (fixedLoadReg):
        regLoad = "r1"
    else:
        regLoad = None
    regStore = "r1"
    regProfileValue = "r0"
    regSignature = "r4"
    regIncrement = "r3"
    regExecCount = "r2"
    regCurrBssAddr = "r5"
    regSync1 = "r4"
    regSync2 = "r3"
    regSync3 = "r0"
    regSync4 = "r1"
    regSync5 = "r6"

    savedRegs = ["r4", "r5", "r6"]  # TODO: Add should-be-preserved registers as you use above
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
        armList = []
        pathCount = 0  # Accumulated number of different value-sets
        profileCount = 0  # Accumulated number of profile statements
        signatureFlushCount = 0  # How many times the signature has been flushed to memory (i.e., number of words for each signature - 1)
        if (profileFP != None):
            profileFP.write("Thread %d Word %d\n" % (thread, signatureFlushCount))

        # Prologue code
        armList.append("@@ Start of generated code")
        armList.append("#include \"%s\"" % (headerName))
        armList.append("    .section .text")
        armList.append("    .globl thread%d_routine" % (thread))
        armList.append("    .globl thread%d_length" % (thread))
        armList.append("    .type thread%d_routine, %%function" % (thread))
        armList.append("thread%d_routine:" % (thread))
        armList.append("@@ Prologue code")
        armList.append("t%d_prologue:" % (thread))
        if (platform == "baremetal"):
            if (thread != numCores-1):
                armList.append("    movw sp,#0x%X" % (low16(stackPointer[thread])))
                if (stackPointer[thread] >= 0x10000):
                    armList.append("    movt sp,#0x%X" % (high16(stackPointer[thread])))
                armList.append("    @ Disable all traps (linux kernel:arch/arm/kernel/hyp-stub.S)")
                armList.append("    mov r7,#0")
                armList.append("    mcr p15, 4, r7, c1, c1, 0  @ HCR")
                armList.append("    mcr p15, 4, r7, c1, c1, 2  @ HCPTR")
                armList.append("    mcr p15, 4, r7, c1, c1, 3  @ HSTR")
                armList.append("    mcr p15, 4, r7, c1, c0, 0  @ HSCTLR")
                armList.append("    mrc p15, 4, r7, c1, c1, 1  @ HDCR")
                armList.append("    and r7, #0x1f              @ Preserve HPMN")
                armList.append("    mcr p15, 4, r7, c1, c1, 1  @ HDCR")
                armList.append("    @ Switch to SVC mode")
                armList.append("    mrs r9,cpsr")
                armList.append("    bic r9,r9,#0x1F")
                armList.append("    orr r9,r9,#(0xC0 | 0x13)  @ [7]: I, [6]: F, [4:0]: M")
                armList.append("    orr r9,r9,#0x100  @ [8]: A")
                armList.append("    adr lr, 1f")
                armList.append("    msr spsr_cxsf,r9")
                armList.append("    .word 0xE12EF30E  @ msr ELR_hyp,lr")
                armList.append("    .word 0xE160006E  @ eret")
                armList.append("1:")
                armList.append("    @ Setting up caches and MMU")
                armList.append("    movw r0,#:lower16:PAGE_TABLE_BASE_1")
                armList.append("    movt r0,#:upper16:PAGE_TABLE_BASE_1")
                armList.append("    movw r2,#:lower16:setup_svc_cache_mmu")
                armList.append("    movt r2,#:upper16:setup_svc_cache_mmu")
                armList.append("    blx r2")
                armList.append("    @ Notify test manager that secondary core is booted")
                armList.append("    movw r0,#:lower16:thread_boot_lock")
                armList.append("    movt r0,#:upper16:thread_boot_lock")
                armList.append("    mov r1,#1")
                armList.append("    str r1,[r0]")
            else:
                for reg in savedRegs:
                    armList.append("    push {%s}" % reg)
            armList.append("    @ Waiting for start flag from test manager")
            armList.append("    movw r0,#:lower16:thread_spawn_lock")
            armList.append("    movt r0,#:upper16:thread_spawn_lock")
            armList.append("1:  ldrex r1,[r0]")
            armList.append("    add r1,r1,#1")
            armList.append("    strex r2,r1,[r0]")
            armList.append("    cmp r2,#0")
            armList.append("    bne 1b")
            armList.append("1:  movw r0,#:lower16:thread_spawn_lock")
            armList.append("    movt r0,#:upper16:thread_spawn_lock")
            armList.append("    ldr r1,[r0]")
            armList.append("    cmp r1,#NUM_THREADS")
            armList.append("    bne 1b")
            if (thread != numCores-1):
                armList.append("    mov r0,#0x0  @ hyp_mode=0")
            else:
                armList.append("    mov r0,#0x1  @ hyp_mode=1")
            armList.append("    movw r2,#:lower16:enable_perfcounter")
            armList.append("    movt r2,#:upper16:enable_perfcounter")
            armList.append("    blx r2")
        elif (platform == "linuxpthread"):
            for reg in savedRegs:
                armList.append("    push {%s}" % reg)
        armList.append("    mov %s,#0" % (regExecCount))

        # Main procedure
        armList.append("@@ Main code")
        armList.append("t%d_exec_loop:" % (thread))
        armList.append("#ifdef EXEC_SYNC")
        armList.append("    @ Execution synchronization")
        armList.append("    @  %s: address of counter / counter pointer" % (regSync1))
        armList.append("    @  %s: counter pointer (indicating counter0 or counter1)" % (regSync2))
        armList.append("    @      When decrementing      | When busy-waiting")
        armList.append("    @  %s: previous counter value | up-to-date value" % (regSync3))
        armList.append("    @  %s: new counter value      | previous value" % (regSync4))
        armList.append("    movw %s,#:lower16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    movt %s,#:upper16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    ldr %s,[%s]" % (regSync2,regSync1))
        armList.append("    cmp %s,#0" % (regSync2))
        armList.append("    movweq %s,#:lower16:thread_exec_barrier0" % (regSync1))
        armList.append("    movteq %s,#:upper16:thread_exec_barrier0" % (regSync1))
        armList.append("    movwne %s,#:lower16:thread_exec_barrier1" % (regSync1))
        armList.append("    movtne %s,#:upper16:thread_exec_barrier1" % (regSync1))
        armList.append("")
        armList.append("    @ Decrementing counter")
        armList.append("1:  ldrex %s,[%s]" % (regSync3,regSync1))
        armList.append("    add %s,%s,#1" % (regSync4,regSync3))
        armList.append("    strex %s,%s,[%s]" % (regSync3,regSync4,regSync1))
        armList.append("    cmp %s,#0" % (regSync3))
        armList.append("    bne 1b")
        armList.append("")
        armList.append("    @ Check if it is last")
        armList.append("    cmp %s,#NUM_THREADS" % (regSync4))
        armList.append("    bne 2f")
        armList.append("")
        armList.append("    @@ (Fall through) Last thread")
        # regSync3: data location index
        # regSync4: data value
        # regSync5: address
        armList.append("    @ Initialize test data section")
        armList.append("    mov  %s,#0" % (regSync3))
        armList.append("1:  mov  %s,%s" % (regSync4,regSync3))
        armList.append("    movt %s,#0xFFFF" % (regSync4))
        armList.append("    movw %s,#:lower16:TEST_DATA_SECTION" % (regSync5))
        armList.append("    movt %s,#:upper16:TEST_DATA_SECTION" % (regSync5))
        if (strideType == 0):
            armList.append("    str %s,[%s,%s,LSL#2]  @ NOTE: this must be manually changed to match with static address generation, strideType = 0" % (regSync4,regSync5,regSync3))
        elif (strideType == 1):
            armList.append("    str %s,[%s,%s,LSL#4]  @ NOTE: this must be manually changed to match with static address generation, strideType = 1" % (regSync4,regSync5,regSync3))
        elif (strideType == 2):
            armList.append("    str %s,[%s,%s,LSL#6]  @ NOTE: this must be manually changed to match with static address generation, strideType = 2" % (regSync4,regSync5,regSync3))
        else:
            assert(False)
        armList.append("    add %s,%s,#1" % (regSync3,regSync3))
        armList.append("    cmp %s,#NUM_SHARED_DATA" % (regSync3))
        armList.append("    blo 1b")
        armList.append("    @ Modify pointer then initialize the old counter")
        armList.append("    @ NOTE: Make sure to follow this order (pointer -> counter)")
        armList.append("    eor %s,%s,#0x1" % (regSync2,regSync2))
        armList.append("    movw %s,#:lower16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    movt %s,#:upper16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    str %s,[%s]" % (regSync2,regSync1))
        armList.append("    cmp %s,#0  @ %s contains new pointer" % (regSync2,regSync2))
        armList.append("    movweq %s,#:lower16:thread_exec_barrier1" % (regSync1))
        armList.append("    movteq %s,#:upper16:thread_exec_barrier1" % (regSync1))
        armList.append("    movwne %s,#:lower16:thread_exec_barrier0" % (regSync1))
        armList.append("    movtne %s,#:upper16:thread_exec_barrier0" % (regSync1))
        armList.append("    mov %s,#0" % (regSync3))
        armList.append("    str %s,[%s]" % (regSync3,regSync1))
        armList.append("    b 3f")
        armList.append("")
        armList.append("2:  @@ Non-last thread")
        armList.append("    movw %s,#:lower16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    movt %s,#:upper16:thread_exec_barrier_ptr" % (regSync1))
        armList.append("    ldr %s,[%s]  @ %s indicates new pointer" % (regSync1,regSync1,regSync1))
        armList.append("    cmp %s,%s    @ %s indicates old pointer" % (regSync1,regSync2,regSync2))
        armList.append("    beq 2b")
        armList.append("")
        armList.append("3:  dmb")
        armList.append("    @ End of execution synchronization")
        armList.append("#endif")
        armList.append("    mov %s,#0" % (regSignature))
        for intermediateCode in intermediate[thread]:
            if (verbosity > 1):
                print("Code: %s" % (intermediateCode))
            armList.append("    @ %s" % intermediateCode)
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
                armList.append("    movw %s,#0x%X" % (regAddr, low16(absAddr)))
                if (absAddr >= 0x10000):
                    armList.append("    movt %s,#0x%X" % (regAddr, high16(absAddr)))
                # 2. load data from memory
                armList.append("    ldr %s,[%s]" % (regLoad, regAddr))
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
                armList.append("    movw %s,#0x%X" % (regAddr, low16(absAddr)))
                if (absAddr >= 0x10000):
                    armList.append("    movt %s,#0x%X" % (regAddr, high16(absAddr)))
                # 2. value to be stored
                armList.append("    movw %s,#0x%X" % (regStore, low16(intermediateCode["value"])))
                if (intermediateCode["value"] >= 0x10000):
                    armList.append("    movt %s,#0x%X" % (regStore, high16(intermediateCode["value"])))
                # 3. store data to memory
                armList.append("    str %s,[%s]" % (regStore, regAddr))
            elif (intermediateCode["type"] == "profile"):
                # reg, targets
                if (not fixedLoadReg):
                    regLoad = "r%d" % intermediateCode["reg"]
                armList.append("    @ accumulated path count: %d" % pathCount)
                # 1. Flushing signature if overflow
                if ((pathCount * len(intermediateCode["targets"])) > ((1 << regBitWidth) - 1)):
                    armList.append("    @ flushing current signature for overflow")
                    armList.append("    movw %s,#:lower16:(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
                    armList.append("    movt %s,#:upper16:(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
                    armList.append("    add %s,%s,#%d" % (regCurrBssAddr, regCurrBssAddr, signatureFlushCount * regBitWidth / 8))
                    armList.append("    str %s,[%s,%s,LSL#%d]" % (regSignature, regCurrBssAddr, regExecCount, math.log(signatureSize, 2)))
                    armList.append("    mov %s,#0x0" % (regSignature))
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
                    armList.append("    movw %s,#0x%X" % (regIncrement, low16(increment)))
                    if (increment >= 0x10000):
                        armList.append("    movt %s,#0x%X" % (regIncrement, high16(increment)))
                    armList.append("    movw %s,#0x%X" % (regProfileValue, low16(target)))
                    if (target >= 0x10000):
                        armList.append("    movt %s,#0x%X" % (regProfileValue, high16(target)))
                    armList.append("    cmp %s,%s" % (regLoad, regProfileValue))
                    armList.append("    beq t%d_p%d_done" % (thread, profileCount))
                    if (profileFP != None):
                        weightTargetDict[increment] = target
                    targetIdx += 1
                armList.append("    b t%d_assert_invalid_value" % (thread))
                armList.append("t%d_p%d_done:" % (thread, profileCount))
                armList.append("    add %s,%s,%s" % (regSignature, regSignature, regIncrement))
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
        armList.append("    movw %s,#:lower16:(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
        armList.append("    movt %s,#:upper16:(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD)" % (regCurrBssAddr, threadIdx))
        armList.append("    add %s,%s,#%d" % (regCurrBssAddr, regCurrBssAddr, signatureFlushCount * regBitWidth / 8))
        armList.append("    str %s,[%s,%s,LSL#%d]" % (regSignature, regCurrBssAddr, regExecCount, math.log(signatureSize, 2)))
        # Fill zero for upper signature (assuming that BSS is not initialized to 0)
        for i in range((signatureFlushCount + 1) * regBitWidth / 8, signatureSize, regBitWidth / 8):
            armList.append("    add %s,%s,#%d" % (regCurrBssAddr, regCurrBssAddr, regBitWidth / 8))
            armList.append("    mov %s,#0" % (regSignature))
            armList.append("    str %s,[%s,%s,LSL#%d]" % (regSignature, regCurrBssAddr, regExecCount, math.log(signatureSize, 2)))

        armList.append("    add %s,%s,#1" % (regExecCount, regExecCount))
        armList.append("    cmp %s,#%d" % (regExecCount, numExecutions))
        armList.append("    blo t%d_exec_loop" % (thread))
        # Epilogue code
        armList.append("@@ Epilogue code")
        armList.append("t%d_epilogue:" % (thread))
        armList.append("    b t%d_test_done" % (thread))
        armList.append("t%d_assert_invalid_value:" % (thread))
        armList.append("    b t%d_assert_invalid_value" % (thread))
        armList.append("t%d_test_done:" % (thread))
        if (platform == "linuxpthread"):
            for reg in reversed(savedRegs):
                armList.append("    pop {%s}" % reg)
            armList.append("    mov pc,lr")
        elif (platform == "baremetal"):
            if (thread != numCores-1):
                armList.append("    mov r0,#0x0  @ hyp_mode=0")
            else:
                armList.append("    mov r0,#0x1  @ hyp_mode=1")
            armList.append("    movw r2,#:lower16:disable_perfcounter")
            armList.append("    movt r2,#:upper16:disable_perfcounter")
            armList.append("    blx r2")
            armList.append("    movw r0,#:lower16:PERF_OUTPUT_T%d" % (thread))
            armList.append("    movt r0,#:upper16:PERF_OUTPUT_T%d" % (thread))
            armList.append("    movw r2,#:lower16:print_perfcounter")
            armList.append("    movt r2,#:upper16:print_perfcounter")
            armList.append("    blx r2")
            armList.append("    movw r0,#:lower16:thread_join_lock")
            armList.append("    movt r0,#:upper16:thread_join_lock")
            armList.append("1:  ldrex r1,[r0]")
            armList.append("    sub r1,r1,#1")
            armList.append("    strex r2,r1,[r0]")
            armList.append("    cmp r2,#0")
            armList.append("    bne 1b")
            if (thread != numCores-1):
                armList.append("    movw r2,#:lower16:clean_invalidate_dcache")
                armList.append("    movt r2,#:upper16:clean_invalidate_dcache")
                armList.append("    blx r2")
                armList.append("    b .  @ halt")
            else:
                armList.append("    mov pc,lr  @ return")
        armList.append("thread%d_length: .word . - thread%d_routine + 0x20  @ FIXME: 0x20 is added to copy constants possibly appended at the end of code" % (thread, thread))
        armList.append("@@ End of generated code")
        armList.append("@ vim: ft=arm")

        if (profileFP != None):
            for emptySignatureWordIdx in range(signatureFlushCount+1,signatureSize / (regBitWidth / 8)):
                profileFP.write("Thread %d Word %d\n" % (thread, emptySignatureWordIdx))

        # Assembly code writing
        asmFP = open(textName, "w")
        for asm in armList:
            asmFP.write("%s\n" % asm)
        asmFP.close()
        if (verbosity > 0):
            print("Assembly file %s generated" % textName)

        threadIdx += 1

    if (profileFP != None):
        profileFP.close()

def header_arm(headerPath, threadList, dataBase, memLocs, bssBase, resultBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, platform, noPrint, expOriginalTime):
    headerString  = ""
    headerString += "/* Test configurations */\n"
    if (platform == "baremetal"):
        headerString += "//#define CORTEX_A7_A7\n"
        headerString += "//#define CORTEX_A15_A15\n"
        headerString += "//#define CORTEX_A7_A15\n"
        headerString += "#define ENABLE_MMU_CACHES\n"
    headerString += "#define EXEC_SYNC\n"
    if (noPrint):
        headerString += "#define NO_PRINT\n"
    else:
        headerString += "//#define NO_PRINT\n"
    if (expOriginalTime):
        headerString += "#define EXP_ORIGINAL_TIME\n"
    else:
        headerString += "//#define EXP_ORIGINAL_TIME\n"
    headerString += "/* Test parameters */\n"
    headerString += "#define NUM_THREADS                 %d\n" % len(threadList)
    headerString += "#define EXECUTION_COUNT             %d\n" % numExecutions
    headerString += "#define NUM_SHARED_DATA             %d\n" % memLocs
    headerString += "#define SIGNATURE_SIZE_IN_BYTE      %d\n" % signatureSize
    headerString += "#define SIGNATURE_SIZE_IN_WORD      (%d/%d)\n" % (signatureSize, regBitWidth / 8)
    headerString += "/* Address map */\n"
    if (platform == "baremetal"):
        headerString += "#define TEST_TEXT_SECTION           0x%X\n" % 0x44000000
        headerString += "#define TEST_THREAD_MAX_SIZE        0x100000\n"
        headerString += "#define TEST_THREAD_BASE(x)         (TEST_TEXT_SECTION + x * TEST_THREAD_MAX_SIZE)\n"
    headerString += "#define TEST_DATA_SECTION           0x%X\n" % dataBase
    if (platform == "baremetal"):
        headerString += "#define TEST_TEXT_SECTION_END       (TEST_DATA_SECTION)\n"
    headerString += "#define TEST_DATA_LOCATIONS         0x10000\n"
    headerString += "#define TEST_BSS_SECTION            0x%X\n" % bssBase
    headerString += "#define TEST_BSS_SIZE_PER_THREAD    0x%X\n" % bssSizePerThread
    if (platform == "baremetal"):
        headerString += "#define TEST_HASH_KEY_TABLE         0x%X\n" % 0x80000000
        headerString += "#define TEST_BSS_SECTION_END        (TEST_HASH_KEY_TABLE)\n"
        headerString += "#define TEST_HASH_VALUE_TABLE       0x%X\n" % 0xA0000000
        headerString += "#define PAGE_TABLE_BASE_0           0xBE9F0000\n"
        headerString += "#define PAGE_TABLE_BASE_1           0xBE9F4000\n"
        headerString += "#define PAGE_TABLE_BASE_2           0xBE9F8000\n"
        headerString += "#define PAGE_TABLE_BASE_3           0xBE9FC000\n"
        headerString += "/* Debug memory map */\n"
        headerString += "#define HASH_RESULT                 0x%X\n" % (resultBase + 0x10 * 0)
        headerString += "#define PERF_OUTPUT_MAIN            0x%X\n" % (resultBase + 0x10 * 1)
        for t in range(len(threadList)):
            headerString += "#define PERF_OUTPUT_T%d              0x%X\n" % (t, resultBase + 0x10 * (t+2))

    headerFP = open(headerPath, "w")
    headerFP.write(headerString)
    headerFP.close()

def manager_arm(cppName, headerName, threadList, signatureSize, regBitWidth, numCores, strideType):
    cppString  = ""
    cppString += "#include \"%s\"\n" % headerName
    cppString += "\n"
    cppString += "/*\n"
    cppString += " * Memory-mapped SoC registers\n"
    cppString += " */\n"
    cppString += "// Addresses\n"
    cppString += "#define EXYNOS5422_PA_SYSRAM_NS 0x02073000\n"
    cppString += "#define HOTPLUG_ADDR            (EXYNOS5422_PA_SYSRAM_NS + 0x1C)\n"
    cppString += "#define EXYNOS5_PA_PMU          0x10040000\n"
    cppString += "#define ARM_CORE_CONFIG_REG(id) (EXYNOS5_PA_PMU + 0x2000 + (0x80 * (id)))\n"
    cppString += "#define ARM_CORE_STATUS_REG(id) (ARM_CORE_CONFIG_REG(id) + 0x4)\n"
    cppString += "#define ARM_CORE_OPTION_REG(id) (ARM_CORE_CONFIG_REG(id) + 0x8)\n"
    cppString += "#define EXYNOS5422_LPI_MASK0    (EXYNOS5_PA_PMU + 0x0004)\n"
    cppString += "#define EXYNOS5422_LPI_MASK1    (EXYNOS5_PA_PMU + 0x0008)\n"
    cppString += "#define EXYNOS5422_ARM_INTR_SPREAD_ENABLE (EXYNOS5_PA_PMU + 0x0100)\n"
    cppString += "#define EXYNOS5422_ARM_INTR_SPREAD_USE_STANDBYWFI (EXYNOS5_PA_PMU + 0x0104)\n"
    cppString += "#define EXYNOS5422_UP_SCHEDULER (EXYNOS5_PA_PMU + 0x0120)\n"
    cppString += "#define EXYNOS5422_CENTRAL_SEQ_OPTION (EXYNOS5_PA_PMU + 0x0208)\n"
    cppString += "#define EXYNOS_SWRESET          (EXYNOS5_PA_PMU + 0x0400)\n"
    cppString += "#define EXYNOS_PMU_SPARE2       (EXYNOS5_PA_PMU + 0x0908)\n"
    cppString += "#define EXYNOS_PMU_SPARE3       (EXYNOS5_PA_PMU + 0x090C)\n"
    cppString += "#define EXYNOS5422_ARM_COMMON_OPTION (EXYNOS5_PA_PMU + 0x2508)\n"
    cppString += "#define EXYNOS5422_KFC_COMMON_OPTION (EXYNOS5_PA_PMU + 0x2588)\n"
    cppString += "#define EXYNOS5422_ARM_L2_OPTION (EXYNOS5_PA_PMU + 0x2608)\n"
    cppString += "#define EXYNOS5422_KFC_L2_OPTION (EXYNOS5_PA_PMU + 0x2688)\n"
    cppString += "#define EXYNOS5422_LOGIC_RESET_DURATION3 (EXYNOS5_PA_PMU + 0x2D1C)\n"
    cppString += "#define EXYNOS5422_PS_HOLD_CONTROL (EXYNOS5_PA_PMU + 0x330C)\n"
    cppString += "\n"
    cppString += "// Values\n"
    cppString += "#define EXYNOS5_USE_RETENTION (1 << 4)\n"
    cppString += "#define EXYNOS_ENABLE_AUTOMATIC_WAKEUP (1 << 8)\n"
    cppString += "#define EXYNOS_CORE_LOCAL_PWR_EN 0x3\n"
    cppString += "#define EXYNOS5422_SWRESET_KFC_SEL 0x3\n"
    cppString += "#define EXYNOS5422_ATB_ISP_ARM (1 << 19)\n"
    cppString += "#define EXYNOS5422_DIS (1 << 15)\n"
    cppString += "#define EXYNOS5422_ATB_KFC (1 << 13)\n"
    cppString += "#define EXYNOS5_SKIP_DEACTIVATE_ACEACP_IN_PWDN (1 << 7)\n"
    cppString += "#define EXYNOS_PS_HOLD_OUTPUT_HIGH (3 << 8)\n"
    cppString += "#define EXYNOS_PS_HOLD_EN (1 << 9)\n"
    cppString += "#define SPREAD_ENABLE 0xF\n"
    cppString += "#define SPREAD_USE_STANDWFI 0xF\n"
    cppString += "#define DUR_WAIT_RESET 0xF\n"
    cppString += "#define EXYNOS5422_USE_STANDBY_WFI_ALL ((0xF << 8) | (0xF << 4))\n"
    cppString += "#define EXYNOS_USE_DELAYED_RESET_ASSERTION (1 << 12)\n"
    cppString += "#define SMC_CMD_CPU1BOOT (-4)\n"
    cppString += "\n"
    cppString += "#define BOOT_CORE_ID 4\n"
    cppString += "#define NUM_CORES 8\n"
    cppString += "\n"
    cppString += "#define NULL 0\n"
    cppString += "\n"
    cppString += "/*\n"
    cppString += " * Test-thread parameters\n"
    cppString += " */\n"
    cppString += "\n"
    for thread in threadList:
        cppString += "extern \"C\" void thread%d_routine();\n" % thread
    for thread in threadList:
        cppString += "extern \"C\" unsigned int thread%d_length;\n" % thread
    cppString += "\n"
    cppString += "int test_manager();\n"
    cppString += "int copy_text_section(unsigned int *src, unsigned int size, unsigned int *tgt);\n"
    cppString += "void classify_result_linear();\n"
    cppString += "void classify_result_binary(bool copy_signatures);\n"
    cppString += "int loop_func();\n"
    cppString += "void inline switch_to_svcmode();\n"
    cppString += "extern \"C\" int setup_sdtt_page_table(unsigned int address);\n"
    cppString += "extern \"C\" int setup_ldtt_page_table(unsigned int address);\n"
    cppString += "extern \"C\" int setup_hyp_cache_mmu(unsigned int address);\n"
    cppString += "extern \"C\" int setup_svc_cache_mmu(unsigned int address);\n"
    cppString += "extern \"C\" void enable_perfcounter(int hyp_mode);\n"
    cppString += "extern \"C\" void disable_perfcounter(int hyp_mode);\n"
    cppString += "extern \"C\" int print_perfcounter(unsigned int *address);\n"
    cppString += "extern \"C\" void invalidate_dcache();\n"
    cppString += "extern \"C\" void clean_invalidate_dcache();\n"
    cppString += "void print_result();\n"
    cppString += "\n"
    cppString += "void delay_us(unsigned int us);\n"
    cppString += "void delay_ms(unsigned int ms);\n"
    cppString += "\n"
    cppString += "void check_regs();\n"
    cppString += "void check_hyp();\n"
    cppString += "extern \"C\" void check_cacheinfo();\n"
    cppString += "\n"
    cppString += "// Non-zero base address wakes up core\n"
    #cppString += "#ifdef CORTEX_A7_A7\n"
    #cppString += "static unsigned int threadBaseAddr[NUM_CORES] = {\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,  // ignored: boot-strap core\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(0),\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(1),\n"
    #cppString += "    0x0\n"
    #cppString += "};\n"
    #cppString += "#else\n"
    #cppString += "#ifdef CORTEX_A7_A15\n"
    #cppString += "static unsigned int threadBaseAddr[NUM_CORES] = {\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(0),\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,  // ignored: boot-strap core\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(1),\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0\n"
    #cppString += "};\n"
    #cppString += "#else\n"
    #cppString += "#ifdef CORTEX_A15_A15\n"
    #cppString += "static unsigned int threadBaseAddr[NUM_CORES] = {\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(0),\n"
    #cppString += "    (unsigned int) TEST_THREAD_BASE(1),\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,  // ignored: boot-strap core\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0,\n"
    #cppString += "    0x0\n"
    #cppString += "};\n"
    #cppString += "#endif\n"
    #cppString += "#endif\n"
    #cppString += "#endif\n"
    # Core-allocation order: Cortex-A15 (core 0->3), Cortex-A7 (core 3->0)
    cppString += "volatile static unsigned int threadBaseAddr[NUM_CORES] = {\n"
    if (len(threadList) > 0):
        cppString += "    (unsigned int) TEST_THREAD_BASE(0),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 1):
        cppString += "    (unsigned int) TEST_THREAD_BASE(1),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 2):
        cppString += "    (unsigned int) TEST_THREAD_BASE(2),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 3):
        cppString += "    (unsigned int) TEST_THREAD_BASE(3),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 7):
        cppString += "    0x0,  // boot-strap core will call a test thread in test_manager()\n"
    else:
        cppString += "    0x0,  // boot-strap core\n"
    if (len(threadList) > 6):
        cppString += "    (unsigned int) TEST_THREAD_BASE(6),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 5):
        cppString += "    (unsigned int) TEST_THREAD_BASE(5),\n"
    else:
        cppString += "    0x0,\n"
    if (len(threadList) > 4):
        cppString += "    (unsigned int) TEST_THREAD_BASE(4),\n"
    else:
        cppString += "    0x0,\n"
    cppString += "};\n"
    cppString += "\n"
    cppString += "volatile int thread_spawn_lock = 0;\n"
    cppString += "volatile int thread_boot_lock = 0;\n"
    cppString += "volatile int thread_join_lock = 0;  // incremented when spawning thread, decremented when thread is done\n"
    cppString += "#ifdef EXEC_SYNC\n"
    cppString += "volatile int __attribute__((aligned(64))) thread_exec_barrier0 = 0;\n"
    cppString += "volatile int __attribute__((aligned(64))) thread_exec_barrier1 = 0;\n"
    cppString += "volatile int __attribute__((aligned(64))) thread_exec_barrier_ptr = 0;\n"
    cppString += "#endif\n"
    cppString += "\n"
    cppString += "unsigned int curr_key[NUM_THREADS * SIGNATURE_SIZE_IN_WORD];  // [number of threads] * [number of word for signature per thread]\n"
    cppString += "volatile unsigned int result[4];\n"
    cppString += "\n"
    cppString += "struct item\n"
    cppString += "{\n"
    cppString += "    unsigned int sig[NUM_THREADS * SIGNATURE_SIZE_IN_WORD];\n"
    cppString += "    unsigned int count;\n"
    cppString += "    struct item *left, *right;\n"
    cppString += "    int balance; /* -1, 0, or +1 */\n"
    cppString += "};\n"
    cppString += "\n"
    cppString += "struct item *root;\n"
    #cppString += "unsigned int hash_size;\n"
    #cppString += "unsigned int hash_size = 0;\n"
    cppString += "volatile unsigned int hash_size = 0;\n"
    cppString += "unsigned int *sort_table_ptr;\n"
    cppString += "\n"
    cppString += "int main()\n"
    cppString += "{\n"
    cppString += "    // 1. Copy text section of test threads\n"
    threadIdx = 0
    for thread in threadList:
        cppString += "    copy_text_section((unsigned int *) thread%d_routine, thread%d_length, (unsigned int *) TEST_THREAD_BASE(%d));\n" % (thread, thread, threadIdx)
        threadIdx += 1
    cppString += "\n"
    cppString += "    // 2. Run test program\n"
    cppString += "    setup_sdtt_page_table(PAGE_TABLE_BASE_1);\n"
    cppString += "    test_manager();\n"
    #cppString += "    return 0;\n"  # FIXME
    cppString += "\n"
    cppString += "    // 3. Analyze test results\n"
    cppString += "    setup_ldtt_page_table(PAGE_TABLE_BASE_0);\n"
    cppString += "    setup_hyp_cache_mmu(PAGE_TABLE_BASE_0);\n"
    cppString += "#ifndef EXP_ORIGINAL_TIME\n"
    cppString += "    //classify_result_linear();\n"
    cppString += "    classify_result_binary(true);\n"
    cppString += "#endif\n"
    cppString += "\n"
    cppString += "    // 4. Write results in memory\n"
    cppString += "    print_perfcounter((unsigned int *)PERF_OUTPUT_MAIN);\n"
    cppString += "    print_result();\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int test_manager()\n"
    cppString += "{\n"
    cppString += "    /* Initialization */\n"
    cppString += "    volatile unsigned int *address;\n"
    cppString += "\n"
    cppString += "    // Test data section\n"
    cppString += "    unsigned int *data_address = (unsigned int *) TEST_DATA_SECTION;\n"
    #cppString += "    for (int i = 0; i < TEST_DATA_LOCATIONS; i++) {\n"
    cppString += "    for (int i = 0; i < NUM_SHARED_DATA; i++) {\n"
    cppString += "        *data_address = (unsigned int) (0xFFFF0000 | i);\n"
    if (strideType == 0):
        cppString += "        data_address++;  // strideType = 0\n"
    elif (strideType == 1):
        cppString += "        data_address+=4;  // strideType = 1\n"
    elif (strideType == 2):
        cppString += "        data_address+=16;  // strideType = 2\n"
    else:
        assert(False)
    cppString += "    }\n"
    cppString += "    asm volatile (\"dmb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_CENTRAL_SEQ_OPTION;\n"
    cppString += "    *address = EXYNOS5422_USE_STANDBY_WFI_ALL;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_L2_OPTION;\n"
    cppString += "    *address &= ~EXYNOS5_USE_RETENTION;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_KFC_L2_OPTION;\n"
    cppString += "    *address &= ~EXYNOS5_USE_RETENTION;\n"
    cppString += "\n"
    cppString += "    /*\n"
    cppString += "     * To increase the stability of KFC reset we need to program\n"
    cppString += "     * the PMU SPARE3 register\n"
    cppString += "     */\n"
    cppString += "    address = (unsigned int *) EXYNOS_PMU_SPARE3;\n"
    cppString += "    *address = EXYNOS5422_SWRESET_KFC_SEL;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_LPI_MASK0;\n"
    cppString += "    *address |= (EXYNOS5422_ATB_ISP_ARM | EXYNOS5422_DIS);\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_LPI_MASK1;\n"
    cppString += "    *address |= EXYNOS5422_ATB_KFC;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_COMMON_OPTION;\n"
    cppString += "    *address |= EXYNOS5_SKIP_DEACTIVATE_ACEACP_IN_PWDN;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_PS_HOLD_CONTROL;\n"
    cppString += "    *address |= EXYNOS_PS_HOLD_OUTPUT_HIGH;\n"
    cppString += "    *address |= EXYNOS_PS_HOLD_EN;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_LOGIC_RESET_DURATION3;\n"
    cppString += "    *address = DUR_WAIT_RESET;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_INTR_SPREAD_ENABLE; \n"
    cppString += "    *address = SPREAD_ENABLE;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_INTR_SPREAD_USE_STANDBYWFI;\n"
    cppString += "    *address = SPREAD_USE_STANDWFI;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_UP_SCHEDULER;\n"
    cppString += "    *address = 0x1;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_COMMON_OPTION;\n"
    cppString += "    *address |= ((1 << 30) | (1 << 29) | (1 << 9));\n"
    cppString += "\n"
    cppString += "    for (int i = 0; i < 8; i++) {\n"
    cppString += "        address = (unsigned int *) ARM_CORE_OPTION_REG(i);\n"
    cppString += "        *address &= ~EXYNOS_USE_DELAYED_RESET_ASSERTION;\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_ARM_COMMON_OPTION;\n"
    cppString += "    *address |= EXYNOS_USE_DELAYED_RESET_ASSERTION;\n"
    cppString += "\n"
    cppString += "    address = (unsigned int *) EXYNOS5422_KFC_COMMON_OPTION;\n"
    cppString += "    *address |= EXYNOS_USE_DELAYED_RESET_ASSERTION;\n"
    cppString += "\n"
    cppString += "    for (int i = 0; i < 8; i++) {\n"
    cppString += "        address = (unsigned int *) ARM_CORE_OPTION_REG(i);\n"
    cppString += "        *address &= ~EXYNOS_ENABLE_AUTOMATIC_WAKEUP;\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    thread_spawn_lock = 0;\n"
    cppString += "    thread_join_lock = 0;\n"
    cppString += "#ifdef EXEC_SYNC\n"
    cppString += "    thread_exec_barrier0 = 0;\n"
    cppString += "    thread_exec_barrier1 = 0;\n"
    cppString += "    thread_exec_barrier_ptr = 0;\n"
    cppString += "#endif\n"
    cppString += "\n"
    cppString += "    /* Spawning test threads */\n"
    cppString += "    /* Adopted from http://stackoverflow.com/questions/20055754/arm-start-wakeup-bringup-the-other-cpu-cores-aps-and-pass-execution-start-addre */\n"
    cppString += "    for (int coreID = 0; coreID < NUM_CORES; coreID++) {\n"
    cppString += "\n"
    cppString += "        if (coreID == BOOT_CORE_ID || threadBaseAddr[coreID] == 0x0) {\n"
    cppString += "            continue;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        thread_boot_lock = 0;\n"
    cppString += "        thread_join_lock++;\n"
    cppString += "\n"
    cppString += "        // 1. Hot-plug thread's base address\n"
    cppString += "        address = (unsigned int *) HOTPLUG_ADDR;\n"
    cppString += "        *address = 0;\n"
    cppString += "\n"
    cppString += "        // 2. Power on\n"
    cppString += "        address = (unsigned int *) ARM_CORE_CONFIG_REG(coreID);\n"
    cppString += "        *address = (unsigned int) EXYNOS_CORE_LOCAL_PWR_EN;\n"
    cppString += "        for (int i = 0; i < 10; i++) {\n"
    cppString += "            address = (unsigned int *) ARM_CORE_STATUS_REG(coreID);\n"
    cppString += "            if ((*address) & EXYNOS_CORE_LOCAL_PWR_EN == EXYNOS_CORE_LOCAL_PWR_EN) {\n"
    cppString += "                break;\n"
    cppString += "            }\n"
    cppString += "            delay_ms(1);\n"
    cppString += "        }\n"
    cppString += "        address = (unsigned int *) ARM_CORE_STATUS_REG(coreID);\n"
    cppString += "        if ((*address) & EXYNOS_CORE_LOCAL_PWR_EN != EXYNOS_CORE_LOCAL_PWR_EN) {\n"
    cppString += "            // failed\n"
    cppString += "            return 1;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        // 3. Software reset\n"
    cppString += "        if (coreID >= 4) {\n"
    cppString += "            address = (unsigned int *) EXYNOS_PMU_SPARE2;\n"
    cppString += "            while (!(*address)) {\n"
    cppString += "                delay_us(10);\n"
    cppString += "            }\n"
    cppString += "            delay_us(10);\n"
    cppString += "\n"
    cppString += "            address = (unsigned int *) EXYNOS_SWRESET;\n"
    cppString += "            *address = (unsigned int) ((1 << 20) | (1 << 8)) << (coreID - 4);\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        // 4. Wakeup the powered-on CPU\n"
    cppString += "        asm volatile (\"dmb\" : : : \"memory\");\n"
    cppString += "        address = (unsigned int *) HOTPLUG_ADDR;\n"
    cppString += "        *address = threadBaseAddr[coreID];\n"
    cppString += "        asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "        asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "        asm volatile (\"sev\" : : : \"memory\");\n"
    cppString += "        asm volatile (\"nop\");\n"
    cppString += "\n"
    cppString += "        while (thread_boot_lock == 0) ;\n"
    cppString += "    }\n"
    cppString += "\n"
    if (len(threadList) == numCores):
        cppString += "    /* Run test thread */\n"
        cppString += "    thread_join_lock++;\n"
        cppString += "    void (*test_thread_routine)(void);\n"
        cppString += "    test_thread_routine = (void (*)())TEST_THREAD_BASE(%d);\n" % (numCores-1)
        cppString += "    test_thread_routine();\n"
        cppString += "\n"
    cppString += "    /* Waiting for test threads to finish */\n"
    cppString += "    while (thread_join_lock > 0) ;\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int copy_text_section(unsigned int *src, unsigned int size, unsigned int *tgt)\n"
    cppString += "{\n"
    cppString += "    unsigned int *end = (unsigned int *) (src + size / sizeof(unsigned int));\n"
    cppString += "\n"
    cppString += "    if (size > TEST_THREAD_MAX_SIZE)\n"
    cppString += "        return 1;\n"
    cppString += "    if ((unsigned int) end > TEST_TEXT_SECTION_END)\n"
    cppString += "        return 1;\n"
    cppString += "\n"
    cppString += "    while ((unsigned int) src < (unsigned int) end) {\n"
    cppString += "        *(tgt++) = *(src++);\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void classify_result_linear()\n"
    cppString += "{\n"
    cppString += "    enable_perfcounter(1);\n"
    cppString += "\n"
    cppString += "    /* Hash function */\n"
    cppString += "    hash_size = 0;\n"
    cppString += "    for (int i = 0; i < EXECUTION_COUNT; i++) {\n"
    cppString += "        unsigned int bss_addr, hash_key_addr, hash_value_addr;  // NOTE: This is not pointer-typed\n"
    cppString += "\n"
    cppString += "        // 1. Collect signatures (\"current key\") from all threads\n"
    cppString += "        for (int t = 0; t < NUM_THREADS; t++) {\n"
    cppString += "            bss_addr = TEST_BSS_SECTION + t * TEST_BSS_SIZE_PER_THREAD + i * %d;\n" % signatureSize
    cppString += "            for (int w = 0; w < %d; w++) {\n" % (signatureSize / (regBitWidth / 8))
    cppString += "                curr_key[t*%d+w] = *(unsigned int *) bss_addr;\n" % (signatureSize / (regBitWidth / 8))
    cppString += "                bss_addr += %d;\n" % (regBitWidth / 8)
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        // 2. Compare each key in the hash table if it is equal to the current key\n"
    cppString += "        int hash_ptr = -1;\n"
    cppString += "        for (int h = 0; h < hash_size; h++) {\n"
    cppString += "            bool found = true;\n"
    cppString += "            hash_key_addr = TEST_HASH_KEY_TABLE + h * (NUM_THREADS * %d);\n" % (signatureSize)
    cppString += "            for (int j = 0; j < NUM_THREADS * %d; j++) {\n" % (signatureSize / (regBitWidth / 8))
    cppString += "                if (curr_key[j] != *(unsigned int *) hash_key_addr) {\n"
    cppString += "                    found = false;\n"
    cppString += "                    break;\n"
    cppString += "                }\n"
    cppString += "                hash_key_addr += 4;\n"
    cppString += "            }\n"
    cppString += "            if (found) {\n"
    cppString += "                hash_ptr = h;\n"
    cppString += "                break;\n"
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        // 3. (If not found) Add the current key into the hash table (with value 1)\n"
    cppString += "        //    Or (If found), increase the hash value by 1 at the existing key\n"
    cppString += "        if (hash_ptr == -1) {\n"
    cppString += "            hash_key_addr = TEST_HASH_KEY_TABLE + hash_size * (NUM_THREADS * %d);\n" % (signatureSize)
    cppString += "            for (int j = 0; j < NUM_THREADS * %d; j++) {\n" % (signatureSize / (regBitWidth / 8))
    cppString += "                *(unsigned int *) hash_key_addr = curr_key[j];\n"
    cppString += "                hash_key_addr += 4;\n"
    cppString += "            }\n"
    cppString += "            hash_value_addr = TEST_HASH_VALUE_TABLE + hash_size * 4;\n"
    cppString += "            *(unsigned int *) hash_value_addr = 1;\n"
    cppString += "            hash_size++;\n"
    cppString += "        } else {\n"
    cppString += "            hash_value_addr = TEST_HASH_VALUE_TABLE + hash_ptr * 4;\n"
    cppString += "            (*(unsigned int *) hash_value_addr)++;\n"
    cppString += "        }\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    // Verify sum of hash values\n"
    cppString += "    unsigned int sumHashValue = 0;\n"
    cppString += "    for (int h = 0; h < hash_size; h++) {\n"
    cppString += "        unsigned int *hashValuePtr = (unsigned int *) (TEST_HASH_VALUE_TABLE + h * 4);\n"
    cppString += "        sumHashValue += *hashValuePtr;\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    result[0] = hash_size;\n"
    cppString += "    result[1] = sumHashValue;\n"
    cppString += "\n"
    cppString += "    disable_perfcounter(1);\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int sigcmp (unsigned int *a, unsigned int *b)\n"
    cppString += "{\n"
    cppString += "    for (int i = 0; i < NUM_THREADS * SIGNATURE_SIZE_IN_WORD; i++) {\n"
    cppString += "        if (*a < *b)\n"
    cppString += "            return -1;\n"
    cppString += "        else if (*a > *b)\n"
    cppString += "            return 1;\n"
    cppString += "        else {\n"
    cppString += "            a++;\n"
    cppString += "            b++;\n"
    cppString += "        }\n"
    cppString += "    }\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "struct item *new_item (unsigned int *sig_param)\n"
    cppString += "{\n"
    cppString += "    unsigned int address = TEST_HASH_KEY_TABLE + hash_size * sizeof(struct item);\n"
    cppString += "    struct item *item_ptr = (struct item *) address;\n"
    cppString += "\n"
    cppString += "    for (int i = 0; i < NUM_THREADS * SIGNATURE_SIZE_IN_WORD; i++) {\n"
    cppString += "        item_ptr->sig[i] = (sig_param != NULL) ? *(sig_param++) : 0;\n"
    cppString += "    }\n"
    cppString += "    item_ptr->count = (sig_param != NULL) ? 1 : 0;\n"
    cppString += "    item_ptr->left = NULL;\n"
    cppString += "    item_ptr->right = NULL;\n"
    cppString += "    item_ptr->balance = 0;\n"
    cppString += "    hash_size++;\n"
    cppString += "    return item_ptr;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void binary_search_item (struct item *root, unsigned int *sig)\n"
    cppString += "{\n"
    cppString += "    /* Algorithm adopted from tsort.c */\n"
    cppString += "    struct item *p, *q, *r, *s, *t;\n"
    cppString += "    int a;\n"
    cppString += "\n"
    cppString += "    if (root->right == NULL) {\n"
    cppString += "        root->right = new_item (sig);\n"
    cppString += "        return;\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    t = root;\n"
    cppString += "    s = p = root->right;\n"
    cppString += "\n"
    cppString += "    while (true)\n"
    cppString += "    {\n"
    cppString += "        a = sigcmp (sig, p->sig);\n"
    cppString += "        if (a == 0) {\n"
    cppString += "            p->count++;\n"
    cppString += "            return;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        if (a < 0)\n"
    cppString += "            q = p->left;\n"
    cppString += "        else\n"
    cppString += "            q = p->right;\n"
    cppString += "\n"
    cppString += "        if (q == NULL)\n"
    cppString += "        {\n"
    cppString += "            /* Add new element */\n"
    cppString += "            q = new_item (sig);\n"
    cppString += "\n"
    cppString += "            if (a < 0)\n"
    cppString += "                p->left = q;\n"
    cppString += "            else\n"
    cppString += "                p->right = q;\n"
    cppString += "\n"
    cppString += "            if (sigcmp (sig, s->sig) < 0)\n"
    cppString += "            {\n"
    cppString += "                r = p = s->left;\n"
    cppString += "                a = -1;\n"
    cppString += "            }\n"
    cppString += "            else\n"
    cppString += "            {\n"
    cppString += "                r = p = s->right;\n"
    cppString += "                a = 1;\n"
    cppString += "            }\n"
    cppString += "\n"
    cppString += "            while (p != q)\n"
    cppString += "            {\n"
    cppString += "                /* doowon: previously p->balance was 0 */\n"
    cppString += "                if (sigcmp (sig, p->sig) < 0)\n"
    cppString += "                {\n"
    cppString += "                    p->balance = -1;\n"
    cppString += "                    p = p->left;\n"
    cppString += "                }\n"
    cppString += "                else\n"
    cppString += "                {\n"
    cppString += "                    p->balance = 1;\n"
    cppString += "                    p = p->right;\n"
    cppString += "                }\n"
    cppString += "            }\n"
    cppString += "\n"
    cppString += "            /* Either tree was balanced or\n"
    cppString += "               adding new node makes the tree balanced */\n"
    cppString += "            if (s->balance == 0 || s->balance == -a)\n"
    cppString += "            {\n"
    cppString += "                s->balance += a;\n"
    cppString += "                return;\n"
    cppString += "            }\n"
    cppString += "\n"
    cppString += "            /* Reorganizing tree */\n"
    cppString += "            if (r->balance == a)\n"
    cppString += "            {\n"
    cppString += "                p = r;\n"
    cppString += "                if (a < 0)\n"
    cppString += "                {\n"
    cppString += "                    s->left = r->right;\n"
    cppString += "                    r->right = s;\n"
    cppString += "                }\n"
    cppString += "                else\n"
    cppString += "                {\n"
    cppString += "                    s->right = r->left;\n"
    cppString += "                    r->left = s;\n"
    cppString += "                }\n"
    cppString += "                s->balance = r->balance = 0;\n"
    cppString += "            }\n"
    cppString += "            else\n"
    cppString += "            {\n"
    cppString += "                /* doowon: I did not fully get this section of code */\n"
    cppString += "                if (a < 0)\n"
    cppString += "                {\n"
    cppString += "                    p = r->right;\n"
    cppString += "                    r->right = p->left;\n"
    cppString += "                    p->left = r;\n"
    cppString += "                    s->left = p->right;\n"
    cppString += "                    p->right = s;\n"
    cppString += "                }\n"
    cppString += "                else\n"
    cppString += "                {\n"
    cppString += "                    p = r->left;\n"
    cppString += "                    r->left = p->right;\n"
    cppString += "                    p->right = r;\n"
    cppString += "                    s->right = p->left;\n"
    cppString += "                    p->left = s;\n"
    cppString += "                }\n"
    cppString += "\n"
    cppString += "                s->balance = 0;\n"
    cppString += "                r->balance = 0;\n"
    cppString += "                if (p->balance == a)\n"
    cppString += "                    s->balance = -a;\n"
    cppString += "                else if (p->balance == -a)\n"
    cppString += "                    r->balance = a;\n"
    cppString += "                p->balance = 0;\n"
    cppString += "            }\n"
    cppString += "\n"
    cppString += "            if (s == t->right)\n"
    cppString += "                t->right = p;\n"
    cppString += "            else\n"
    cppString += "                t->left = p;\n"
    cppString += "\n"
    cppString += "            return;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        /* Find the closest imbalanced node */\n"
    cppString += "        if (q->balance)\n"
    cppString += "        {\n"
    cppString += "            t = p;\n"
    cppString += "            s = q;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        /* Iterate to next level */\n"
    cppString += "        p = q;\n"
    cppString += "    }\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void copy_sorted_signatures(struct item *curr)\n"
    cppString += "{\n"
    cppString += "    if (curr->left != NULL)\n"
    cppString += "        copy_sorted_signatures(curr->left);\n"
    cppString += "    if (curr->count != 0)\n"
    cppString += "        for (int i = 0; i < NUM_THREADS * SIGNATURE_SIZE_IN_WORD; i++)\n"
    cppString += "            *(sort_table_ptr++) = curr->sig[i];\n"
    cppString += "    if (curr->right != NULL)\n"
    cppString += "        copy_sorted_signatures(curr->right);\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void classify_result_binary(bool copy_signatures)\n"
    cppString += "{\n"
    cppString += "    enable_perfcounter(1);\n"
    cppString += "\n"
    cppString += "    hash_size = 0;\n"
    cppString += "    root = new_item(NULL);\n"
    cppString += "    hash_size = 1;\n"
    cppString += "\n"
    cppString += "    /* Hash function */\n"
    cppString += "    for (int i = 0; i < EXECUTION_COUNT; i++) {\n"
    cppString += "        unsigned int bss_addr, hash_key_addr, hash_value_addr;  // NOTE: This is not pointer-typed\n"
    cppString += "\n"
    cppString += "        // 1. Collect signatures (\"current key\") from all threads\n"
    cppString += "        for (int t = 0; t < NUM_THREADS; t++) {\n"
    cppString += "            bss_addr = TEST_BSS_SECTION + t * TEST_BSS_SIZE_PER_THREAD + i * SIGNATURE_SIZE_IN_WORD * sizeof(unsigned int);\n"
    cppString += "            for (int w = 0; w < SIGNATURE_SIZE_IN_WORD; w++) {\n"
    cppString += "                curr_key[t*SIGNATURE_SIZE_IN_WORD+w] = *(unsigned int *) bss_addr;\n"
    cppString += "                bss_addr += sizeof(unsigned int);\n"
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        // 2. Binary-search keys in the hash table if it is equal to current key\n"
    cppString += "        //    If not found, add current key into hash table (with value 1)\n"
    cppString += "        binary_search_item (root, curr_key);\n"
    cppString += "        // hash_size is increased in this function\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    // Verify sum of hash values\n"
    cppString += "    unsigned int sumHashValue = 0;\n"
    cppString += "    for (int h = 0; h < hash_size; h++) {\n"
    cppString += "        unsigned int address = TEST_HASH_KEY_TABLE + h * sizeof(struct item);\n"
    cppString += "        struct item *item_ptr = (struct item *) address;\n"
    cppString += "        sumHashValue += item_ptr->count;\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    result[2] = (hash_size - 1);\n"
    cppString += "    result[3] = sumHashValue;\n"
    cppString += "\n"
    cppString += "    disable_perfcounter(1);\n"
    cppString += "\n"
    cppString += "    if (copy_signatures) {\n"
    cppString += "        sort_table_ptr = (unsigned int *) TEST_HASH_VALUE_TABLE; // hash_size variable is recycled\n"
    cppString += "        copy_sorted_signatures(root);\n"
    cppString += "        result[0] = NUM_THREADS * SIGNATURE_SIZE_IN_WORD;\n"
    cppString += "        result[1] = (unsigned int) sort_table_ptr;\n"
    cppString += "    }\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int loop_func()\n"
    cppString += "{\n"
    cppString += "    //volatile int count = 0;\n"
    cppString += "    //int count = 0;\n"
    cppString += "    volatile unsigned int *count_ptr = (unsigned int *) 0x80000000;\n"
    cppString += "    for (unsigned int i = 0; i < 0x2000000; i++) {\n"
    cppString += "        //count++;\n"
    cppString += "        (*count_ptr)++;\n"
    cppString += "    }\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void inline switch_to_svcmode()\n"
    cppString += "{\n"
    cppString += "    asm volatile (\n"
    cppString += "        \"mov r7,#0\\n\\t\"\n"
    cppString += "        \"mcr p15, 4, r7, c1, c1, 0  @ HCR\\n\\t\"\n"
    cppString += "        \"mcr p15, 4, r7, c1, c1, 2  @ HCPTR\\n\\t\"\n"
    cppString += "        \"mcr p15, 4, r7, c1, c1, 3  @ HSTR\\n\\t\"\n"
    cppString += "        \"mcr p15, 4, r7, c1, c0, 0  @ HSCTLR\\n\\t\"\n"
    cppString += "        \"mrc p15, 4, r7, c1, c1, 1  @ HDCR\\n\\t\"\n"
    cppString += "        \"and r7, #0x1f              @ Preserve HPMN\\n\\t\"\n"
    cppString += "        \"mcr p15, 4, r7, c1, c1, 1  @ HDCR\\n\\t\"\n"
    cppString += "        \"@ Switch to SVC mode\\n\\t\"\n"
    cppString += "        \"mrs r9,cpsr\\n\\t\"\n"
    cppString += "        \"bic r9,r9,#0x1F\\n\\t\"\n"
    cppString += "        \"orr r9,r9,#(0xC0 | 0x13)  @ [7]: I, [6]: F, [4:0]: M\\n\\t\"\n"
    cppString += "        \"orr r9,r9,#0x100  @ [8]: A\\n\\t\"\n"
    cppString += "        \"adr lr, 1f\\n\\t\"\n"
    cppString += "        \"msr spsr_cxsf,r9\\n\\t\"\n"
    cppString += "        \".word 0xE12EF30E  @ msr ELR_hyp,lr\\n\\t\"\n"
    cppString += "        \".word 0xE160006E  @ eret\\n\\t\"\n"
    cppString += "    \"1:\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void invalidate_branchpredictor()\n"
    cppString += "{\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c7, c5, 6\" : : \"r\" (0));\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void invalidate_icache()\n"
    cppString += "{\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c7, c5, 0\" : : \"r\" (0));\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void invalidate_dcache()\n"
    cppString += "{\n"
    cppString += "    for (int level = 0; level < 2; level++) {\n"
    cppString += "        unsigned int sscidr, dcisw;\n"
    cppString += "        //unsigned int *address = (unsigned int *) 0x40000090;\n"
    cppString += "\n"
    cppString += "        asm volatile (\"mcr p15, 2, %0, c0, c0, 0\" : : \"r\" ((level << 1) | 0x0));  // CSSELR\n"
    cppString += "        asm volatile (\"mrc p15, 1, %0, c0, c0, 0\" : \"=r\" (sscidr) );\n"
    cppString += "\n"
    cppString += "        int log2_line_len = ((sscidr >> 0) & 0x7) + 2 + 2;  // e.g., [2:0]=0b001 means 8 words per line, so 32 bytes.\n"
    cppString += "        int temp_num_ways = (sscidr >> 3) & 0x3FF; // e.g., [12:3]=0b0000000001 means 2 ways\n"
    cppString += "        int num_ways = temp_num_ways + 1;\n"
    cppString += "        int num_sets = ((sscidr >> 13) & 0x7FFF) + 1;\n"
    cppString += "        int log2_num_ways = 0;\n"
    cppString += "\n"
    cppString += "        // e.g.1., temp_num_ways = 0b1 (2 ways) -> log2_num_ways = 1\n"
    cppString += "        // e.g.2., temp_num_ways = 0b111 (8 ways) -> log2_num_ways = 3\n"
    cppString += "        // e.g.3., temp_num_ways = 0x101 (6 ways) -> log2_num_ways = 3\n"
    cppString += "        while (temp_num_ways > 0) {\n"
    cppString += "            log2_num_ways++;\n"
    cppString += "            temp_num_ways >>= 1;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        //*(address++) = num_ways;\n"
    cppString += "        //*(address++) = num_sets;\n"
    cppString += "\n"
    cppString += "        for (int way = 0; way < num_ways; way++) {\n"
    cppString += "            for (int set = 0; set < num_sets; set++) {\n"
    cppString += "                dcisw = (way << (32-log2_num_ways)) | (set << log2_line_len) | (level << 1);\n"
    cppString += "                asm volatile (\"mcr p15, 0, %0, c7, c6, 2\" : : \"r\" (dcisw));\n"
    cppString += "                //*(address++) = dcisw;\n"
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void clean_invalidate_dcache()\n"
    cppString += "{\n"
    cppString += "    for (int level = 0; level < 2; level++) {\n"
    cppString += "        unsigned int sscidr, dccisw;\n"
    cppString += "        //unsigned int *address = (unsigned int *) 0x40000090;\n"
    cppString += "\n"
    cppString += "        asm volatile (\"mcr p15, 2, %0, c0, c0, 0\" : : \"r\" ((level << 1) | 0x0));  // CSSELR\n"
    cppString += "        asm volatile (\"mrc p15, 1, %0, c0, c0, 0\" : \"=r\" (sscidr) );\n"
    cppString += "\n"
    cppString += "        int log2_line_len = ((sscidr >> 0) & 0x7) + 2 + 2;  // e.g., [2:0]=0b001 means 8 words per line, so 32 bytes.\n"
    cppString += "        int temp_num_ways = (sscidr >> 3) & 0x3FF; // e.g., [12:3]=0b0000000001 means 2 ways\n"
    cppString += "        int num_ways = temp_num_ways + 1;\n"
    cppString += "        int num_sets = ((sscidr >> 13) & 0x7FFF) + 1;\n"
    cppString += "        int log2_num_ways = 0;\n"
    cppString += "\n"
    cppString += "        // e.g.1., temp_num_ways = 0b1 (2 ways) -> log2_num_ways = 1\n"
    cppString += "        // e.g.2., temp_num_ways = 0b111 (8 ways) -> log2_num_ways = 3\n"
    cppString += "        // e.g.3., temp_num_ways = 0x101 (6 ways) -> log2_num_ways = 3\n"
    cppString += "        while (temp_num_ways > 0) {\n"
    cppString += "            log2_num_ways++;\n"
    cppString += "            temp_num_ways >>= 1;\n"
    cppString += "        }\n"
    cppString += "\n"
    cppString += "        //*(address++) = num_ways;\n"
    cppString += "        //*(address++) = num_sets;\n"
    cppString += "\n"
    cppString += "        for (int way = 0; way < num_ways; way++) {\n"
    cppString += "            for (int set = 0; set < num_sets; set++) {\n"
    cppString += "                dccisw = (way << (32-log2_num_ways)) | (set << log2_line_len) | (level << 1);\n"
    cppString += "                asm volatile (\"mcr p15, 0, %0, c7, c14, 2\" : : \"r\" (dccisw));\n"
    cppString += "                //*(address++) = dccisw;\n"
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void invalidate_tlb()\n"
    cppString += "{\n"
    cppString += "    // Reference: u-boot-odroidxu3/arch/arm/cpu/armv7/cache_v7.c\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c8, c7, 0\" : : \"r\" (0));\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c8, c6, 0\" : : \"r\" (0));\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c8, c5, 0\" : : \"r\" (0));\n"
    cppString += "    asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int setup_ldtt_page_table(unsigned int address)\n"
    cppString += "{\n"
    cppString += "    // Setting up page table (entire address space)\n"
    cppString += "    unsigned int *page_table = (unsigned int *) address;\n"
    cppString += "\n"
    cppString += "    // Descriptors (block type)\n"
    cppString += "    // [54]: XN\n"
    cppString += "    // [53]: PXN\n"
    cppString += "    // [52]: Contiguous hint\n"
    cppString += "    // [11]: nG\n"
    cppString += "    // [10]: AF\n"
    cppString += "    // [9:8]: SH[1:0] (00: non-shareable, 01: unpredictable, 10: outer, 11: inner shareable)\n"
    cppString += "    // [7:6]: AP[2:1]\n"
    cppString += "    // [5]: NS\n"
    cppString += "    // [4:2]: AttrIndx[2:0]\n"
    cppString += "\n"
    cppString += "    // I only define for lower 32 bits, because the upper 32 bits are all 0s\n"
    cppString += "    unsigned int device_descriptor, memory_descriptor;\n"
    cppString += "\n"
    cppString += "    device_descriptor = (0x1 << 10) | (0x3 << 8) | (0x1 << 6) | (0x0 << 2) | (0x1 << 0);  // AF=1, SH=11, AP=01, AttrIndx=000 (device), block type\n"
    cppString += "    //device_descriptor = (0x1 << 10) | (0x2 << 8) | (0x1 << 6) | (0x0 << 2) | (0x1 << 0);  // AF=1, SH=10, AP=01, AttrIndx=000 (device), block type\n"
    cppString += "    //device_descriptor = (0x1 << 10) | (0x0 << 8) | (0x1 << 6) | (0x0 << 2) | (0x1 << 0);  // AF=1, SH=00, AP=01, AttrIndx=000 (device), block type\n"
    cppString += "    memory_descriptor = (0x1 << 10) | (0x3 << 8) | (0x1 << 6) | (0x1 << 2) | (0x1 << 0);  // AF=1, SH=11, AP=01, AttrIndx=001 (memory), block type\n"
    cppString += "    //memory_descriptor = (0x1 << 10) | (0x2 << 8) | (0x1 << 6) | (0x1 << 2) | (0x1 << 0);  // AF=1, SH=10, AP=01, AttrIndx=001 (memory), block type\n"
    cppString += "    //memory_descriptor = (0x1 << 10) | (0x0 << 8) | (0x1 << 6) | (0x1 << 2) | (0x1 << 0);  // AF=1, SH=00, AP=01, AttrIndx=001 (memory), block type\n"
    cppString += "\n"
    cppString += "    // 1st 1GB (0x00000000 - 0x3FFFFFFF)\n"
    cppString += "    *(page_table++) = (0x0 << 30) | device_descriptor; // lower\n"
    cppString += "    *(page_table++) = (unsigned int) 0;  // upper\n"
    cppString += "\n"
    cppString += "    // 2nd 1GB (0x40000000 - 0x7FFFFFFF)\n"
    cppString += "    *(page_table++) = (0x1 << 30) | memory_descriptor; // lower\n"
    cppString += "    *(page_table++) = (unsigned int) 0;  // upper\n"
    cppString += "\n"
    cppString += "    // 3rd 1GB (0x80000000 - 0xBFFFFFFF)\n"
    cppString += "    *(page_table++) = (0x2 << 30) | memory_descriptor; // lower\n"
    cppString += "    *(page_table++) = (unsigned int) 0;  // upper\n"
    cppString += "\n"
    cppString += "    // 4th 1GB (0xC0000000 - 0xFFFFFFFF)\n"
    cppString += "    *(page_table++) = (0x3 << 30) | device_descriptor; // lower\n"
    cppString += "    *(page_table++) = (unsigned int) 0;  // upper\n"
    cppString += "\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int setup_sdtt_page_table(unsigned int address)\n"
    cppString += "{\n"
    cppString += "    // This routine initializes page tables in short-descriptor translation table (SDTT) format\n"
    cppString += "    // Use in pair with setup_svc_cache_mmu()\n"
    cppString += "\n"
    cppString += "    unsigned int *page_table = (unsigned int *) address;\n"
    cppString += "\n"
    cppString += "    // Destriptor format\n"
    cppString += "    // [31:20]: Section base address PA[31:20]\n"
    cppString += "    // [19]: NS (non-secure)\n"
    cppString += "    // [18]: 0\n"
    cppString += "    // [17]: nG (not global)\n"
    cppString += "    // [16]: S (shareable)\n"
    cppString += "    // [15]: AP[2] (access permissions)\n"
    cppString += "    // [14:12]: TEX[2:0] (memory region attribute)\n"
    cppString += "    // [11:10]: AP[1:0] (access permissions)\n"
    cppString += "    // [8:5]: Domain\n"
    cppString += "    // [4]: XN (execute never)\n"
    cppString += "    // [3]: C (memory region attribute)\n"
    cppString += "    // [2]: B (memory region attribute)\n"
    cppString += "    // [1]: 1\n"
    cppString += "    // [0]: PXN (privileged execute never)\n"
    cppString += "\n"
    cppString += "    unsigned int base_descriptor = (1 << 16) | (3 << 10) | (2 << 0);\n"
    cppString += "    // S=1 (shareable), AP[2:0]=011 (full access), section block\n"
    cppString += "\n"
    cppString += "    // Setting up page table (1:1 mapping for entire address space)\n"
    cppString += "    for (int i = 0; i < 4096; i++) {\n"
    cppString += "        *(page_table++) = base_descriptor | (i << 20); // strongly ordered\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    // Setting up page table (cacheable)\n"
    cppString += "    unsigned int cacheable_start, cacheable_end;\n"
    cppString += "    //cacheable_start = 0x50000000, cacheable_end = TEST_BSS_SECTION_END;\n"
    cppString += "    cacheable_start = TEST_TEXT_SECTION, cacheable_end = TEST_BSS_SECTION_END;\n"
    cppString += "\n"
    cppString += "    page_table = (unsigned int *) address;\n"
    cppString += "    page_table += (cacheable_start >> 20);\n"
    cppString += "    for (int i = (cacheable_start >> 20); i < (cacheable_end >> 20); i++)\n"
    cppString += "    {\n"
    cppString += "        // TEX[2:0] & C & B: 1AABB (cacheable memory)\n"
    cppString += "        //   AA indicates inner attribute\n"
    cppString += "        //   BB indicates outer attribute\n"
    cppString += "        // For both AA and BB, encoding follows\n"
    cppString += "        //   00: non-cacheable\n"
    cppString += "        //   01: write-back, write-allocate\n"
    cppString += "        //   10: write-through, no write-allocate\n"
    cppString += "        //   11: write-back, no write-allocate\n"
    cppString += "\n"
    cppString += "        *(page_table++) = base_descriptor | (i << 20) | (0x7 << 12) | (0x3 << 2); // outer/inner write-back, no write allocate\n"
    cppString += "        //*(page_table++) = base_descriptor | (i << 20); // strongly ordered\n"
    cppString += "    }\n"
    cppString += "\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"dsb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int setup_hyp_cache_mmu(unsigned int address)\n"
    cppString += "{\n"
    cppString += "    unsigned int hsctlr;\n"
    cppString += "\n"
    cppString += "    // Invalidate branch predictor\n"
    cppString += "    invalidate_branchpredictor();\n"
    cppString += "\n"
    cppString += "    // Invalidate I cache\n"
    cppString += "    invalidate_icache();\n"
    cppString += "\n"
    cppString += "    // Invalidate D cache\n"
    cppString += "    //invalidate_dcache();\n"
    cppString += "    clean_invalidate_dcache();\n"
    cppString += "\n"
    cppString += "    // Invalidate TLBs\n"
    cppString += "    invalidate_tlb();\n"
    cppString += "\n"
    cppString += "    // Disable all traps\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c1, c1, 0\" : : \"r\" (0));  // HCR\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c1, c1, 2\" : : \"r\" (0));  // HCPTR\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c1, c1, 3\" : : \"r\" (0));  // HSTR\n"
    cppString += "\n"
    cppString += "    // MMU setting\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c10, c2, 0\" : : \"r\" ((0xFE << 8) | (0x0 << 0))); // HMAIR0\n"
    cppString += "    //asm volatile (\"mcr p15, 4, %0, c10, c2, 0\" : : \"r\" ((0x44 << 8) | (0x0 << 0))); // HMAIR0 FIXME\n"
    cppString += "    //asm volatile (\"mcr p15, 4, %0, c10, c2, 0\" : : \"r\" ((0x00 << 8) | (0x0 << 0))); // HMAIR0 FIXME\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c10, c2, 1\" : : \"r\" (0)); // HMAIR1\n"
    cppString += "    asm volatile (\"mcrr p15, 4, %0, %1, c2\" : : \"r\" (address), \"r\" (0x0)); // HTTBR\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "#ifdef ENABLE_MMU_CACHES\n"
    cppString += "    // Enable caches and MMU\n"
    cppString += "    asm volatile (\"mrc p15, 4, %0, c1, c0, 0\" : \"=r\" (hsctlr) );\n"
    cppString += "    hsctlr |= (0x1025);  // I, CP15BEN, C, M bits\n"
    cppString += "    asm volatile (\"mcr p15, 4, %0, c1, c0, 0\" : : \"r\" (hsctlr) );\n"
    cppString += "#endif\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int setup_svc_cache_mmu(unsigned int address)\n"
    cppString += "{\n"
    cppString += "    // NOTE: This routine cannot be used in hypervisor mode.\n"
    cppString += "    //       Only use it under supervisor mode.\n"
    cppString += "    unsigned int sctlr, ttbr;\n"
    cppString += "\n"
    cppString += "    // Invalidate branch predictor\n"
    cppString += "    invalidate_branchpredictor();\n"
    cppString += "\n"
    cppString += "    // Invalidate I cache\n"
    cppString += "    invalidate_icache();\n"
    cppString += "\n"
    cppString += "#if 0\n"
    cppString += "    // Invalidate D cache\n"
    cppString += "    //invalidate_dcache();\n"
    cppString += "    clean_invalidate_dcache();\n"
    cppString += "#endif\n"
    cppString += "\n"
    cppString += "    // Invalidate TLBs\n"
    cppString += "    invalidate_tlb();\n"
    cppString += "\n"
    cppString += "    // Setting up control register for page table and access control\n"
    cppString += "    // Reference: u-boot-odroidxu3/arch/arm/lib/cache-cp15.c\n"
    cppString += "    // [31:x]: Translation table base\n"
    cppString += "    // [x-1:7]: Reserved\n"
    cppString += "    // [6]: IRGN[0]\n"
    cppString += "    // [5]: NOS (not outer shareable)\n"
    cppString += "    // [4:3]: RGN (region)\n"
    cppString += "    //        00: normal memory, outer non-cacheable\n"
    cppString += "    //        01: normal memory, outer write-back write-allocate cacheable\n"
    cppString += "    //        10: normal memory, outer write-through cacheable\n"
    cppString += "    //        11: normal memory, outer write-back no write-allocate cacheable\n"
    cppString += "    // [2]: IMP (implementation defined)\n"
    cppString += "    // [1]: S (shareable)\n"
    cppString += "    // [0]: IRGN[1]\n"
    cppString += "    //      IRGN[1:0] 00: normal memory, inner non-cacheable\n"
    cppString += "    //                01: normal memory, inner write-back write-allocate cacheable\n"
    cppString += "    //                10: normal memory, inner write-through cacheable\n"
    cppString += "    //                11: normal memory, inner write-back no write-allocate cacheable\n"
    cppString += "    ttbr = address | (0x4B << 0); // S = 1, RGN=01, IRGN = 11\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c2, c0, 0\" : : \"r\" (ttbr) : \"memory\");\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c3, c0, 0\" : : \"r\" (~0));\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "#ifdef ENABLE_MMU_CACHES\n"
    cppString += "    // MMU & Data cache enable\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c1, c0, 0\" : \"=r\" (sctlr) );\n"
    cppString += "    sctlr |= (1 << 12); // I (instruction cache)\n"
    cppString += "    sctlr |= (1 << 11); // Z (branch prediction enable)\n"
    cppString += "    sctlr |= (1 <<  5); // CP15BEN\n"
    cppString += "    sctlr |= (1 <<  2); // C (data cache)\n"
    cppString += "    sctlr |= (1 <<  0); // M (MMU enable)\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c1, c0, 0\" : : \"r\" (sctlr) );\n"
    cppString += "#endif\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void enable_perfcounter(int hyp_mode)\n"
    cppString += "{\n"
    cppString += "    unsigned int pm;\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 5\" : : \"r\" (0x1F) ); // PMSELR\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c13, 1\" : \"=r\" (pm) ); // PMXEVTYPER\n"
    cppString += "    pm = pm | (1 << 27);\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c13, 1\" : : \"r\" (pm) ); // PMXEVTYPER\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 5\" : : \"r\" (0x0) ); // PMSELR: Counter 0\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c13, 1\" : \"=r\" (pm) ); // PMXEVTYPER\n"
    cppString += "    //pm = pm | (1 << 27) | (0x08 << 0); // evtCount=INST_RETIRED\n"
    cppString += "    //pm = pm | (1 << 27) | (0x13 << 0); // evtCount=MEM_ACCESS(data)\n"
    cppString += "    //pm = pm | (1 << 27) | (0x04 << 0); // evtCount=L1D_CACHE\n"
    cppString += "    pm = pm | (1 << 27) | (0x14 << 0); // evtCount=L1I_CACHE\n"
    cppString += "    //pm = pm | (1 << 27) | (0x16 << 0); // evtCount=L2D_CACHE\n"
    cppString += "    //pm = pm | (1 << 27) | (0x10 << 0); // evtCount=BR_MIS_PRED\n"
    cppString += "    //pm = pm | (1 << 27) | (0x12 << 0); // evtCount=BR_PRED\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c13, 1\" : : \"r\" (pm) ); // PMXEVTYPER\n"
    cppString += "    if (hyp_mode != 0) {\n"
    cppString += "        asm volatile (\"mrc p15, 4, %0, c1, c1, 1\" : \"=r\" (pm) ); // HDCR register\n"
    cppString += "        pm = pm | (1 << 7);  // HDCR.HPME\n"
    cppString += "        asm volatile (\"mcr p15, 4, %0, c1, c1, 1\" : : \"r\" (pm) );\n"
    cppString += "    }\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c14, 0\" : : \"r\" (1)); // PMUSERENR\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c12, 0\" : \"=r\" (pm) ); // PMCR\n"
    cppString += "    pm = pm | (1 << 4) | (1 << 3) | (1 << 0); // X (export enable), D (clock divider), E (enable)\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 0\" : : \"r\" (pm) );\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 1\" : : \"r\" (0x8000000F) ); // PMCNTENSET\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void disable_perfcounter(int hyp_mode)\n"
    cppString += "{\n"
    cppString += "    unsigned int pm;\n"
    cppString += "    if (hyp_mode != 0) {\n"
    cppString += "        asm volatile (\"mrc p15, 4, %0, c1, c1, 1\" : \"=r\" (pm) ); // HDCR register\n"
    cppString += "        pm = pm & ~(1 << 7);  // HDCR.HPME\n"
    cppString += "        asm volatile (\"mcr p15, 4, %0, c1, c1, 1\" : : \"r\" (pm) );\n"
    cppString += "    }\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c12, 0\" : \"=r\" (pm) ); // PMCR\n"
    cppString += "    pm = pm & ~(1 << 0);\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 0\" : : \"r\" (pm) );\n"
    cppString += "    asm volatile (\"mcr p15, 0, %0, c9, c12, 2\" : : \"r\" (0x8000000F) ); // PMCNTENCLR\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "int print_perfcounter(unsigned int *address)\n"
    cppString += "{\n"
    cppString += "    unsigned int pm;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c13, 0\" : \"=r\" (pm) ); // PMCCNTR\n"
    cppString += "    *(address++) = pm;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c13, 1\" : \"=r\" (pm) ); // PMXEVTYPER\n"
    cppString += "    *(address++) = pm;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c13, 2\" : \"=r\" (pm) ); // PMXEVCNTR\n"
    cppString += "    *(address++) = pm;\n"
    cppString += "\n"
    cppString += "    //asm volatile (\"mrc p15, 4, %0, c1, c1, 0\" : \"=r\" (pm)); // HCR\n"
    cppString += "    //asm volatile (\"mrc p15, 4, %0, c1, c1, 2\" : \"=r\" (pm)); // HCPTR\n"
    cppString += "    //asm volatile (\"mrc p15, 4, %0, c1, c1, 3\" : \"=r\" (pm)); // HSTR\n"
    cppString += "    //asm volatile (\"mrc p15, 4, %0, c15, c0, 0\" : \"=r\" (pm)); // CBAR\n"
    cppString += "    //asm volatile (\"mrc p15, 1, %0, c9, c0, 2\" : \"=r\" (pm)); // L2CTLR\n"
    cppString += "    //asm volatile (\"mrs %0,cpsr\" : \"=r\" (pm)); // CPSR\n"
    cppString += "    //*(address++) = pm;\n"
    cppString += "\n"
    cppString += "    //asm volatile (\"mrc p15, 4, %0, c1, c1, 1\" : \"=r\" (pm) ); // HDCR register\n"
    cppString += "    //*(address++) = pm;\n"
    cppString += "    //asm volatile (\"mrc p15, 0, %0, c9, c12, 0\" : \"=r\" (pm) ); // PMCR\n"
    cppString += "    //*(address++) = pm;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c9, c12, 3\" : \"=r\" (pm) ); // PMOVSR\n"
    cppString += "    *(address++) = pm;\n"
    cppString += "    ////asm volatile (\"mrc p15, 0, %0, c9, c12, 4\" : \"=r\" (pm) ); // undefined instruction\n"
    cppString += "    ////*(address++) = pm;\n"
    cppString += "    //asm volatile (\"mrc p15, 0, %0, c9, c12, 5\" : \"=r\" (pm) ); // PMSELR\n"
    cppString += "    //*(address++) = pm;\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "\n"
    cppString += "    return 0;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void check_regs()\n"
    cppString += "{\n"
    cppString += "    unsigned int cpsr;\n"
    cppString += "    unsigned int midr;\n"
    cppString += "    unsigned int tt;\n"
    cppString += "    unsigned int sctlr;\n"
    cppString += "    unsigned int actlr;\n"
    cppString += "    unsigned int *address = (unsigned int *) 0x40000000;\n"
    cppString += "    asm volatile (\"mrs %0, cpsr\" : \"=r\" (cpsr) );  // CPSR\n"
    cppString += "    *(address++) = cpsr;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c0, c0, 0\" : \"=r\" (midr) );  // MIDR\n"
    cppString += "    *(address++) = midr;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c2, c0, 0\" : \"=r\" (tt) );  // TTBR0\n"
    cppString += "    *(address++) = tt;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c2, c0, 1\" : \"=r\" (tt) );  // TTBR1\n"
    cppString += "    *(address++) = tt;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c2, c0, 2\" : \"=r\" (tt) );  // TTBCR\n"
    cppString += "    *(address++) = tt;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c1, c0, 0\" : \"=r\" (sctlr) );  // SCTLR\n"
    cppString += "    *(address++) = sctlr;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c1, c0, 1\" : \"=r\" (actlr) );  // ACTLR\n"
    cppString += "    *(address++) = actlr;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c5, c0, 0\" : \"=r\" (tt) );  // DFSR\n"
    cppString += "    *(address++) = tt;\n"
    cppString += "    asm volatile (\"mrc p15, 0, %0, c5, c0, 1\" : \"=r\" (tt) );  // IFSR\n"
    cppString += "    *(address++) = tt;\n"
    cppString += "    asm volatile (\"isb\" : : : \"memory\");\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void check_hyp()\n"
    cppString += "{\n"
    cppString += "    unsigned int reg;\n"
    cppString += "    unsigned int reg2;\n"
    cppString += "    unsigned int *address = (unsigned int *) 0x40000000;\n"
    cppString += "    asm volatile (\"mrc p15, 4, %0, c1, c0, 0\" : \"=r\" (reg) ); // HSCTLR\n"
    cppString += "    *(address++) = reg;\n"
    cppString += "    asm volatile (\"mrrc p15, 4, %0, %1, c2\" : \"=r\" (reg), \"=r\" (reg2) ); // HTTBR\n"
    cppString += "    *(address++) = reg;\n"
    cppString += "    *(address++) = reg2;\n"
    cppString += "    asm volatile (\"mrc p15, 4, %0, c2, c0, 2\" : \"=r\" (reg) ); // HTCR\n"
    cppString += "    *(address++) = reg;\n"
    cppString += "    asm volatile (\"mrc p15, 4, %0, c10, c2, 0\" : \"=r\" (reg) ); // HMAIR0\n"
    cppString += "    *(address++) = reg;\n"
    cppString += "    asm volatile (\"mrc p15, 4, %0, c10, c2, 1\" : \"=r\" (reg) ); // HMAIR1\n"
    cppString += "    *(address++) = reg;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void check_cacheinfo()\n"
    cppString += "{\n"
    cppString += "    unsigned int value;\n"
    cppString += "    unsigned int *address = (unsigned int *) 0x40000040;\n"
    cppString += "    // CLIDR\n"
    cppString += "    asm volatile (\"mrc p15, 1, %0, c0, c0, 1\" : \"=r\" (value) );\n"
    cppString += "    *(address++) = value;\n"
    cppString += "\n"
    cppString += "    // CCSIDR for L1 instruction cache (CCSELR=0x1)\n"
    cppString += "    asm volatile (\"mcr p15, 2, %0, c0, c0, 0\" : : \"r\" ((0x000 << 1) | 0x1));\n"
    cppString += "    asm volatile (\"mrc p15, 1, %0, c0, c0, 0\" : \"=r\" (value) );\n"
    cppString += "    *(address++) = value;\n"
    cppString += "\n"
    cppString += "    // CCSIDR for L1 data cache (CSSELR=0x0)\n"
    cppString += "    asm volatile (\"mcr p15, 2, %0, c0, c0, 0\" : : \"r\" ((0x000 << 1) | 0x0));\n"
    cppString += "    asm volatile (\"mrc p15, 1, %0, c0, c0, 0\" : \"=r\" (value) );\n"
    cppString += "    *(address++) = value;\n"
    cppString += "\n"
    cppString += "    // CCSIDR for L2 cache (CSSELR=0x2)\n"
    cppString += "    asm volatile (\"mcr p15, 2, %0, c0, c0, 0\" : : \"r\" ((0x001 << 1) | 0x0));\n"
    cppString += "    asm volatile (\"mrc p15, 1, %0, c0, c0, 0\" : \"=r\" (value) );\n"
    cppString += "    *(address++) = value;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void print_result()\n"
    cppString += "{\n"
    cppString += "    unsigned int *address = (unsigned int *) HASH_RESULT;\n"
    cppString += "    *(address++) = result[0];\n"
    cppString += "    *(address++) = result[1];\n"
    cppString += "    *(address++) = result[2];\n"
    cppString += "    *(address++) = result[3];\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "#define DELAY_SCALE_US_SHIFT 9\n"
    cppString += "#define DELAY_SCALE_MS_SHIFT (DELAY_SCALE_US_SHIFT + 4)\n"
    cppString += "\n"
    cppString += "void delay_us(unsigned int us)\n"
    cppString += "{\n"
    cppString += "    volatile unsigned int count = (unsigned int) us << DELAY_SCALE_US_SHIFT;\n"
    cppString += "    while (count > 0)\n"
    cppString += "        count --;\n"
    cppString += "}\n"
    cppString += "\n"
    cppString += "void delay_ms(unsigned int ms)\n"
    cppString += "{\n"
    cppString += "    volatile unsigned int count = (unsigned int) ms << DELAY_SCALE_MS_SHIFT;\n"
    cppString += "    while (count > 0)\n"
    cppString += "        count --;\n"
    cppString += "}\n"

    cppFP = open(cppName, "w")
    cppFP.write(cppString)
    cppFP.close()

