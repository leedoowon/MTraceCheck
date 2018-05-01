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
# rax:
# rcx:
# rdx:
# rbx:
# rsp:
# rbp:
# rsi:
# rdi:
# r8 : memory address / profile value (valid load value)
# r9 : load target / store value
# r10: execution counter
# r11: signature increment
# r12: profiling signature (sum)
# r13: bss address (for storing results)
# r14:
# r15:
#

def test_x86(intermediate, textNamePrefix, textNameSuffix, headerName, dataBase, bssBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, fixedLoadReg, platform, profileName, numCores, strideType, verbosity):

    ####################################################################
    # Text section
    ####################################################################

    ####################################################################
    # See register allocation map above
    regAddr = "%r8d"
    if (fixedLoadReg):
        regLoad = "%r9d"
    else:
        regLoad = None
    regStore = "%r9d"
    regProfileValue = "%r8d"
    regSignature = "%r12"
    regIncrement = "%r11"
    regExecCount = "%r10d"
    regCurrBssAddr = "%r13d"
    regSync1 = "%al"
    regSync2 = "%ah"
    regSync3 = "%ecx"
    regSync4 = "%edx"
    regSync5 = "%ebx"
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
        x86List = []
        pathCount = 0  # Accumulated number of different value-sets
        profileCount = 0  # Accumulated number of profile statements
        signatureFlushCount = 0  # How many times the signature has been flushed to memory (i.e., number of words for each signature - 1)
        if (profileFP != None):
            profileFP.write("Thread %d Word %d\n" % (thread, signatureFlushCount))

        # Prologue code
        x86List.append("## Start of generated code")
        x86List.append("#include \"%s\"" % (headerName))
        if (platform == "linuxpthread"):
            x86List.append("    .section .text")
        elif (platform == "baremetal"):
            x86List.append("#include \"common.h\"")
            x86List.append("    .section .core%d_init" % thread)
        x86List.append("    .globl thread%d_routine" % (thread))
        x86List.append("    .globl thread%d_length" % (thread))
        x86List.append("    .type thread%d_routine, @function" % (thread))
        x86List.append("thread%d_routine:" % (thread))
        if (platform == "baremetal"):
            if (thread != numCores-1):
                x86List.append("    .code16")
                x86List.append("    cli")
                x86List.append("    PROTECTED_MODE")
                x86List.append("    PAGING_IA32E_ON")
                x86List.append("    ENTER_64BIT_MODE")
                x86List.append("    jmp thread%d_text" % (thread))
                x86List.append("    .equ thread%d_length, . - thread%d_routine" % (thread, thread))
            else:
                x86List.append("    jmp thread%d_text" % (thread))
                x86List.append("")
            x86List.append("    .section .test_text")
            x86List.append("thread%d_text:" % (thread))
        x86List.append("## Start synchronization")
        x86List.append("    lock incb thread_spawn_lock")
        x86List.append("wait_for_test_start:")
        x86List.append("    cmpb $NUM_THREADS, thread_spawn_lock")
        x86List.append("    jl wait_for_test_start")
        x86List.append("## Prologue code")
        x86List.append("t%d_prologue:" % (thread))
        x86List.append("    mov $0,%s" % (regExecCount))

        # Main procedure
        x86List.append("## Main code")
        x86List.append("t%d_exec_loop:" % (thread))
        x86List.append("#ifdef EXEC_SYNC")
        x86List.append("    # Execution synchronization")
        x86List.append("    #  %s: counter value" % (regSync1))
        x86List.append("    #  %s: counter pointer (indicating counter0 or counter1)" % (regSync2))
        x86List.append("    mov $1,%s" % (regSync1))
        x86List.append("    mov thread_exec_barrier_ptr,%s" % (regSync2))
        x86List.append("    cmp $0,%s" % (regSync2))
        x86List.append("    jne 2f")
        x86List.append("    lock xadd %s,thread_exec_barrier0" % (regSync1))
        x86List.append("    jmp 1f")
        x86List.append("2:  lock xadd %s,thread_exec_barrier1" % (regSync1))
        x86List.append("1:  # Check if it is last")
        x86List.append("    cmp $NUM_THREADS-1,%s # %s indicates old value" % (regSync1, regSync1))
        x86List.append("    jne 2f")
        x86List.append("    ## (Fall through) Last thread")
        # regSync3: data location index
        # regSync4: data value
        # regSync5: address
        x86List.append("    # Initialize test data section")
        x86List.append("    mov $0,%s" % (regSync3))
        x86List.append("1:  mov $0xFFFF0000,%s" % (regSync4))
        x86List.append("    or %s,%s" % (regSync3,regSync4))
        x86List.append("    mov $TEST_DATA_SECTION,%s" % (regSync5))
        if (strideType == 0):
            # stride = 4
            x86List.append("    lea (%s,%s,4),%s  # NOTE: this must be manually changed to match with static address generation" % (regSync5,regSync3,regSync5))
        elif (strideType == 1):
            # stride = 16
            x86List.append("    lea (%s,%s,8),%s  # NOTE: this must be manually changed to match with static address generation" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
        elif (strideType == 2):
            # stride = 32
            x86List.append("    lea (%s,%s,8),%s  # NOTE: this must be manually changed to match with static address generation" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
            x86List.append("    lea (%s,%s,8),%s" % (regSync5,regSync3,regSync5))
        else:
            assert(False)
        x86List.append("    mov %s,(%s)" % (regSync4,regSync5))
        x86List.append("    inc %s" % (regSync3))
        x86List.append("    cmp $NUM_SHARED_DATA,%s" % (regSync3))
        x86List.append("    jl 1b")
        x86List.append("    # Modify pointer then initialize the old counter")
        x86List.append("    # NOTE: Make sure to follow this order (pointer -> counter)")
        x86List.append("    mov $0,%s" % (regSync1))
        x86List.append("    xor $0x1,%s" % (regSync2))
        x86List.append("    mov %s,thread_exec_barrier_ptr" % (regSync2))
        x86List.append("    cmp $0,%s  # %s is new pointer" % (regSync2, regSync2))
        x86List.append("    jne 1f")
        x86List.append("    mov %s,thread_exec_barrier1" % (regSync1))
        x86List.append("    jmp 3f")
        x86List.append("1:  mov %s,thread_exec_barrier0" % (regSync1))
        x86List.append("    jmp 3f")
        x86List.append("2:  ## Non-last thread")
        x86List.append("    cmp %s,thread_exec_barrier_ptr  # %s indicates old pointer" % (regSync2, regSync2))
        x86List.append("    je 2b")
        x86List.append("3:  mfence")
        x86List.append("    # End of execution synchronization")
        x86List.append("#endif")
        x86List.append("    mov $0,%s" % (regSignature))
        for intermediateCode in intermediate[thread]:
            if (verbosity > 1):
                print("Code: %s" % (intermediateCode))
            x86List.append("    # %s" % intermediateCode)
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
                    regLoad = "r%dd" % intermediateCode["reg"]  # e.g., r8 -> r8d (32-bit)
                # 1. construct effective address from immediate
                x86List.append("    mov $0x%X,%s" % (absAddr, regAddr))
                # 2. load data from memory
                x86List.append("    mov (%s),%s" % (regAddr, regLoad))
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
                x86List.append("    mov $0x%X,%s" % (absAddr, regAddr))
                # 2. value to be stored
                x86List.append("    mov $0x%X,%s" % (intermediateCode["value"], regStore))
                # 3. store data to memory
                x86List.append("    mov %s,(%s)" % (regStore, regAddr))
            # doowon, 2017/09/06, fences added
            elif (intermediateCode["type"] == "fence"):
                x86List.append("    mfence")
            elif (intermediateCode["type"] == "profile"):
                # reg, targets
                if (not fixedLoadReg):
                    regLoad = "r%dd" % intermediateCode["reg"]  # e.g., r8 -> r8d (32-bit)
                x86List.append("    # accumulated path count: %d" % pathCount)
                # 1. Flushing signature if overflow
                if ((pathCount * len(intermediateCode["targets"])) > ((1 << regBitWidth) - 1)):
                    x86List.append("    # flushing current signature for overflow")
                    x86List.append("    mov $(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD + 0x%X),%s" % (threadIdx, signatureFlushCount * regBitWidth / 8, regCurrBssAddr))
                    tempSignatureOffset = signatureSize
                    if (tempSignatureOffset > 8):
                        # If signature is larger than signature offset, it must be a multiple of 8
                        assert(tempSignatureOffset % 8 == 0)
                        while (tempSignatureOffset >= 8):
                            x86List.append("    lea (%s,%s,8),%s" % (regCurrBssAddr, regExecCount, regCurrBssAddr))
                            tempSignatureOffset -= 8
                    else:
                        x86List.append("    lea (%s,%s,%d),%s" % (regCurrBssAddr, regExecCount, signatureSize, regCurrBssAddr))
                    x86List.append("    mov %s,(%s)" % (regSignature, regCurrBssAddr))
                    x86List.append("    mov $0x0,%s" % (regSignature))
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
                    x86List.append("    mov $0x%X,%s" % (increment, regIncrement))
                    x86List.append("    mov $0x%X,%s" % (target, regProfileValue))
                    x86List.append("    cmp %s,%s" % (regProfileValue, regLoad))
                    x86List.append("    jz t%d_p%d_done" % (thread, profileCount))
                    if (profileFP != None):
                        weightTargetDict[increment] = target
                    targetIdx += 1
                x86List.append("    jmp t%d_assert_invalid_value" % (thread))
                x86List.append("t%d_p%d_done:" % (thread, profileCount))
                x86List.append("    add %s,%s" % (regIncrement, regSignature))
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
        # doowon, 2018/02/09, save signature only when there is at least one profile statement
        if profileCount > 0:
            x86List.append("    mov $(TEST_BSS_SECTION + %d * TEST_BSS_SIZE_PER_THREAD + 0x%X),%s" % (threadIdx, signatureFlushCount * regBitWidth / 8, regCurrBssAddr))
            tempSignatureOffset = signatureSize
            if (tempSignatureOffset > 8):
                # If signature is larger than signature offset, it must be a multiple of 8
                assert(tempSignatureOffset % 8 == 0)
                while (tempSignatureOffset >= 8):
                    x86List.append("    lea (%s,%s,8),%s" % (regCurrBssAddr, regExecCount, regCurrBssAddr))
                    tempSignatureOffset -= 8
            else:
                x86List.append("    lea (%s,%s,%d),%s" % (regCurrBssAddr, regExecCount, signatureSize, regCurrBssAddr))
            x86List.append("    mov %s,(%s)" % (regSignature, regCurrBssAddr))

        x86List.append("    inc %s" % (regExecCount))
        x86List.append("    cmp $EXECUTION_COUNT,%s" % (regExecCount))
        x86List.append("    jl t%d_exec_loop" % (thread))
        # Epilogue code
        x86List.append("## Epilogue code")
        x86List.append("t%d_epilogue:" % (thread))
        x86List.append("    jmp t%d_test_done" % (thread))
        x86List.append("t%d_assert_invalid_value:" % (thread))
        x86List.append("    jmp t%d_assert_invalid_value" % (thread))
        x86List.append("t%d_test_done:" % (thread))
        if (platform == "linuxpthread"):
            x86List.append("    ret")
        elif (platform == "baremetal"):
            x86List.append("    lock incb thread_join_lock")
            if (thread != numCores-1):
                x86List.append("    hlt")
            else:
                x86List.append("    # Jump to absolute address")
                x86List.append("    push $wait_for_test_threads")
                x86List.append("    ret")
        x86List.append("## End of generated code")

        if (profileFP != None):
            for emptySignatureWordIdx in range(signatureFlushCount+1,signatureSize / (regBitWidth / 8)):
                profileFP.write("Thread %d Word %d\n" % (thread, emptySignatureWordIdx))

        # Assembly code writing
        asmFP = open(textName, "w")
        for asm in x86List:
            asmFP.write("%s\n" % asm)
        asmFP.close()
        if (verbosity > 0):
            print("Assembly file %s generated" % textName)

        threadIdx += 1

    if (profileFP != None):
        profileFP.close()

def header_x86(headerPath, threadList, dataBase, memLocs, bssBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, platform, noPrint):
    headerString  = ""
    headerString += "/* Test configurations */\n"
    headerString += "#define EXEC_SYNC\n"
    if (noPrint):
        headerString += "#define NO_PRINT\n"
    else:
        headerString += "//#define NO_PRINT\n"
    headerString += "/* Test parameters */\n"
    headerString += "#define NUM_THREADS                %d\n" % len(threadList)
    headerString += "#define EXECUTION_COUNT            %d\n" % numExecutions
    headerString += "#define NUM_SHARED_DATA            %d\n" % memLocs
    headerString += "#define SIGNATURE_SIZE_IN_BYTE     %d\n" % signatureSize
    headerString += "#define SIGNATURE_SIZE_IN_WORD     (%d/%d)\n" % (signatureSize, regBitWidth / 8)
    headerString += "/* Address map */\n"
    if (platform == "baremetal"):
        headerString += "#define thread_spawn_lock          0x2000\n"
        headerString += "#define thread_join_lock           0x2008\n"
        headerString += "#define TEMP_DATA0                 0x2010\n"
        headerString += "#ifdef EXEC_SYNC\n"
        headerString += "#define thread_exec_barrier0       0x2040\n"
        headerString += "#define thread_exec_barrier1       0x2080\n"
        headerString += "#define thread_exec_barrier_ptr    0x20C0\n"
        headerString += "#endif\n"
        headerString += "#define result_addr                0x2100\n"
        headerString += "// result will occupy 4 words\n"
        headerString += "#define hash_size_addr             0x2020\n"
        headerString += "// hashSize will occupy 1 word\n"
        headerString += "#define curr_key_addr              0x2200\n"
        headerString += "// curr_key will occupy NUM_THREADS * SIGNATURE_SIZE_IN_BYTE\n"
        #headerString += "#define TEST_TEXT_SECTION          0x00040000\n"
        #headerString += "#define TEST_THREAD_MAX_SIZE       0x00010000\n"
    #threadIdx = 0
    #for thread in threadList:
    #    headerString += "#define TEST_THREAD_BASE_%d         (TEST_TEXT_SECTION + TEST_THREAD_MAX_SIZE * %d)\n" % (thread, threadIdx)
    #    threadIdx += 1
    headerString += "#define TEST_DATA_SECTION          0x%X\n" % dataBase
    headerString += "#define TEST_DATA_LOCATIONS        0x00010000\n"
    headerString += "#define TEST_BSS_SECTION           0x%X\n" % bssBase
    headerString += "#define TEST_BSS_SIZE_PER_THREAD   0x%X\n" % bssSizePerThread
    if (platform == "baremetal"):
        headerString += "#define TEST_HASH_KEY_TABLE        0x20000000\n"
        headerString += "#define TEST_HASH_VALUE_TABLE      0x30000000\n"
        headerString += "#define TEST_HASH_STACK_BASE       0x30000000\n"

    headerFP = open(headerPath, "w")
    headerFP.write(headerString)
    headerFP.close()

def common_x86(filePath):
    contentString  = ""
    contentString += "/* Base code is adopted from common.h at https://github.com/cirosantilli/x86-bare-metal-examples */\n"
    contentString += ".altmacro\n"
    contentString += "/* Helpers */\n"
    contentString += ".macro PUSH_ADX\n"
    contentString += "    push %ax\n"
    contentString += "    push %bx\n"
    contentString += "    push %cx\n"
    contentString += "    push %dx\n"
    contentString += ".endm\n"
    contentString += ".macro POP_DAX\n"
    contentString += "    pop %dx\n"
    contentString += "    pop %cx\n"
    contentString += "    pop %bx\n"
    contentString += "    pop %ax\n"
    contentString += ".endm\n"
    contentString += ".macro PUSH_EADX\n"
    contentString += "    push %eax\n"
    contentString += "    push %ebx\n"
    contentString += "    push %ecx\n"
    contentString += "    push %edx\n"
    contentString += ".endm\n"
    contentString += ".macro POP_EDAX\n"
    contentString += "    pop %edx\n"
    contentString += "    pop %ecx\n"
    contentString += "    pop %ebx\n"
    contentString += "    pop %eax\n"
    contentString += ".endm\n"
    contentString += ".macro PUSH_RADX\n"
    contentString += "    push %rax\n"
    contentString += "    push %rbx\n"
    contentString += "    push %rcx\n"
    contentString += "    push %rdx\n"
    contentString += ".endm\n"
    contentString += ".macro POP_RDAX\n"
    contentString += "    pop %rdx\n"
    contentString += "    pop %rcx\n"
    contentString += "    pop %rbx\n"
    contentString += "    pop %rax\n"
    contentString += ".endm\n"
    contentString += ".macro HEX_NIBBLE reg\n"
    contentString += "    LOCAL letter, end\n"
    contentString += "    cmp $10, \\reg\n"
    contentString += "    jae letter\n"
    contentString += "    add $'0, \\reg\n"
    contentString += "    jmp end\n"
    contentString += "letter:\n"
    contentString += "    /* 0x37 == 'A' - 10 */\n"
    contentString += "    add $0x37, \\reg\n"
    contentString += "end:\n"
    contentString += ".endm\n"
    contentString += ".macro HEX c\n"
    contentString += "    mov \c, %al\n"
    contentString += "    mov \c, %ah\n"
    contentString += "    shr $4, %al\n"
    contentString += "    HEX_NIBBLE <%al>\n"
    contentString += "    and $0x0F, %ah\n"
    contentString += "    HEX_NIBBLE <%ah>\n"
    contentString += ".endm\n"
    contentString += "/* Structural. */\n"
    contentString += ".macro BEGIN\n"
    contentString += "    LOCAL after_locals\n"
    contentString += "    .code16\n"
    contentString += "    cli\n"
    contentString += "    /* Set %cs to 0. TODO Is that really needed? */\n"
    contentString += "    ljmp $0, $1f\n"
    contentString += "    1:\n"
    contentString += "    xor %ax, %ax\n"
    contentString += "    /* We must zero %ds for any data access. */\n"
    contentString += "    mov %ax, %ds\n"
    contentString += "    /* TODO is it really need to clear all those segment registers, e.g. for BIOS calls? */\n"
    contentString += "    mov %ax, %es\n"
    contentString += "    mov %ax, %fs\n"
    contentString += "    mov %ax, %gs\n"
    contentString += "    /*\n"
    contentString += "    TODO What to move into BP and SP?\n"
    contentString += "    http://stackoverflow.com/questions/10598802/which-value-should-be-used-for-sp-for-booting-process\n"
    contentString += "    */\n"
    contentString += "    mov %ax, %bp\n"
    contentString += "    /* Automatically disables interrupts until the end of the next instruction. */\n"
    contentString += "    mov %ax, %ss\n"
    contentString += "    /* We should set SP because BIOS calls may depend on that. TODO confirm. */\n"
    contentString += "    mov %bp, %sp\n"
    contentString += "    /* Store the initial dl to load stage 2 later on. */\n"
    contentString += "    mov %dl, initial_dl\n"
    contentString += "    jmp after_locals\n"
    contentString += "    initial_dl: .byte 0\n"
    contentString += "after_locals:\n"
    contentString += ".endm\n"
    contentString += ".macro STAGE2\n"
    contentString += "    /* Defined in the linker script. */\n"
    contentString += "    mov $__stage2_nsectors, %al\n"
    contentString += "    mov $0x02, %ah\n"
    contentString += "    mov $1f, %bx\n"
    contentString += "    mov $0x0002, %cx\n"
    contentString += "    mov $0x00, %dh\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "bad:jc bad\n"
    contentString += "    jmp 1f\n"
    contentString += "    .section .stage2\n"
    contentString += "    1:\n"
    contentString += ".endm\n"
    contentString += ".macro STAGE2_LBA\n"
    contentString += "    .equ temp_block, 0x6000\n"
    contentString += "stage2_lba:\n"
    contentString == "    mov $__stage2_nsectors, %ax\n"
    contentString == "    cmp $(66 + 128 * 3), %ax\n"
    contentString == "2:  jg 2b  /* infinite loop: code size overflowed */\n"
    contentString += "    mov $DAP, %si\n"
    contentString += "    mov $0x42, %ah\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "2:  jc 2b  /* infinite loop */\n"
    contentString += "    mov $DAP2, %si\n"
    contentString += "    mov $0x42, %ah\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "2:  jc 2b  /* infinite loop */\n"
    contentString += "    mov $DAP3, %si\n"
    contentString += "    mov $0x42, %ah\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "2:  jc 2b  /* infinite loop */\n"
    contentString += "    mov $DAP4, %si\n"
    contentString += "    mov $0x42, %ah\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "2:  jc 2b  /* infinite loop */\n"
    contentString += "    mov $DAP5, %si\n"
    contentString += "    mov $0x42, %ah\n"
    contentString += "    mov initial_dl, %dl\n"
    contentString += "    int $0x13\n"
    contentString += "2:  jc 2b  /* infinite loop */\n"
    # FIXME: Loading file blocks should be more flexible
    contentString += "    /* Relocate block */\n"
    contentString += "    mov $temp_block, %esi\n"
    contentString += "    mov $0xFE00, %edi\n"
    contentString += "    mov $0x200, %ecx\n"
    contentString += "    rep movsb\n"
    contentString += "    jmp 1f\n"
    contentString += "DAP:.byte 0x10\n"
    contentString += "    .byte 0\n"
    contentString += "    .word 64\n"
    contentString += "    .word 0x7E00 /* lower address */\n"
    contentString += "    .word 0 /* upper address */\n"
    contentString += "    .long 1\n"
    contentString += "    .long 0\n"
    contentString += "DAP2:.byte 0x10\n"
    contentString += "    .byte 0\n"
    contentString += "    .word 1\n"  #
    contentString += "    .word temp_block /* base register bx */\n"
    contentString += "    .word 0x0000 /* segment register es */\n"
    contentString += "    .long 65\n"
    contentString += "    .long 0\n"
    contentString += "DAP3:.byte 0x10\n"
    contentString += "    .byte 0\n"
    contentString += "    .word 128\n"  # OKAY (FAIL FOR GREATER THAN 128)
    contentString += "    .word 0x0000 /* base register bx */\n"
    contentString += "    .word 0x1000 /* segment register es */\n"
    contentString += "    .long 66\n"
    contentString += "    .long 0\n"
    contentString += "DAP4:.byte 0x10\n"
    contentString += "    .byte 0\n"
    contentString += "    .word 128\n"
    contentString += "    .word 0x0000 /* base register bx */\n"
    contentString += "    .word 0x2000 /* segment register es */\n"
    contentString += "    .long 66 + 128\n"
    contentString += "    .long 0\n"
    contentString += "DAP5:.byte 0x10\n"
    contentString += "    .byte 0\n"
    contentString += "    .word 128\n"
    contentString += "    .word 0x0000 /* base register bx */\n"
    contentString += "    .word 0x3000 /* segment register es */\n"
    contentString += "    .long 66 + 256\n"
    contentString += "    .long 0\n"
    contentString += "    .section .stage2\n"
    contentString += "    1:\n"
    contentString += ".endm\n"
    contentString += ".macro PROTECTED_MODE\n"
    contentString += "    /* Must come before they are used. */\n"
    contentString += "    .equ CODE_SEG, 8\n"
    contentString += "    .equ DATA_SEG, gdt_data - gdt_start\n"
    contentString += "    /* Tell the processor where our Global Descriptor Table is in memory. */\n"
    contentString += "start_protected_mode:\n"
    contentString += "    lgdt gdt_descriptor\n"
    contentString += "    /*\n"
    contentString += "    Set PE (Protection Enable) bit in CR0 (Control Register 0),\n"
    contentString += "    effectively entering protected mode.\n"
    contentString += "    */\n"
    contentString += "    mov %cr0, %eax\n"
    contentString += "    orl $0x1, %eax\n"
    contentString += "    mov %eax, %cr0\n"
    contentString += "    ljmp $CODE_SEG, $protected_mode\n"
    contentString += "gdt_start:\n"
    contentString += "gdt_null:\n"
    contentString += "    .long 0x0\n"
    contentString += "    .long 0x0\n"
    contentString += "gdt_code:\n"
    contentString += "    .word 0xffff\n"
    contentString += "    .word 0x0\n"
    contentString += "    .byte 0x0\n"
    contentString += "    .byte 0b10011010\n"
    contentString += "    .byte 0b11001111\n"
    contentString += "    .byte 0x0\n"
    contentString += "gdt_data:\n"
    contentString += "    .word 0xffff\n"
    contentString += "    .word 0x0\n"
    contentString += "    .byte 0x0\n"
    contentString += "    .byte 0b10010010\n"
    contentString += "    .byte 0b11001111\n"
    contentString += "    .byte 0x0\n"
    contentString += "gdt_end:\n"
    contentString += "gdt_descriptor:\n"
    contentString += "    .word gdt_end - gdt_start\n"
    contentString += "    .long gdt_start\n"
    contentString += "vga_current_line:\n"
    contentString += "    .long 0\n"
    contentString += ".code32\n"
    contentString += "protected_mode:\n"
    contentString += "    /*\n"
    contentString += "    Setup the other segments.\n"
    contentString += "    Those movs are mandatory because they update the descriptor cache:\n"
    contentString += "    http://wiki.osdev.org/Descriptor_Cache\n"
    contentString += "    */\n"
    contentString += "    mov $DATA_SEG, %ax\n"
    contentString += "    mov %ax, %ds\n"
    contentString += "    mov %ax, %es\n"
    contentString += "    mov %ax, %fs\n"
    contentString += "    mov %ax, %gs\n"
    contentString += "    mov %ax, %ss\n"
    contentString += "    /*\n"
    contentString += "    TODO detect the last memory address available properly.\n"
    contentString += "    It depends on how much RAM we have.\n"
    contentString += "    */\n"
    contentString += "    mov $0X7000, %ebp\n"
    contentString += "    mov %ebp, %esp\n"
    contentString += ".endm\n"
    contentString += ".macro ENTER_64BIT_MODE\n"
    contentString += "    /* Note: EFER.LME flag is set in PAGING_IA32E_ON */\n"
    contentString += "    /* You must call PAGING_IA32E_ON before calling this */\n"
    contentString += "    .equ CODE_SEG, 8\n"
    contentString += "    .equ DATA_SEG, gdt_64bit_data - gdt_64bit_start\n"
    contentString += "    lgdt gdt_64bit_descriptor\n"
    contentString += "    ljmp $CODE_SEG, $long_mode\n"
    contentString += "gdt_64bit_start:\n"
    contentString += "gdt_64bit_null:\n"
    contentString += "    .long 0x0\n"
    contentString += "    .long 0x0\n"
    contentString += "gdt_64bit_code:\n"
    contentString += "    .word 0xffff\n"
    contentString += "    .word 0x0\n"
    contentString += "    .byte 0x0\n"
    contentString += "    .byte 0b10011010\n"
    contentString += "    #.byte 0b11001111\n"
    contentString += "    .byte 0b10101111\n"
    contentString += "    .byte 0x0\n"
    contentString += "gdt_64bit_data:\n"
    contentString += "    .word 0xffff\n"
    contentString += "    .word 0x0\n"
    contentString += "    .byte 0x0\n"
    contentString += "    .byte 0b10010010\n"
    contentString += "    .byte 0b11001111\n"
    contentString += "    .byte 0x0\n"
    contentString += "gdt_64bit_end:\n"
    contentString += "gdt_64bit_descriptor:\n"
    contentString += "    .word gdt_64bit_end - gdt_64bit_start\n"
    contentString += "    .quad gdt_64bit_start\n"
    contentString += ".code64\n"
    contentString += "long_mode:\n"
    contentString += "    mov $DATA_SEG, %ax\n"
    contentString += "    mov %ax, %ds\n"
    contentString += "    mov %ax, %es\n"
    contentString += "    mov %ax, %fs\n"
    contentString += "    mov %ax, %gs\n"
    contentString += "    mov %ax, %ss\n"
    contentString += ".endm\n"
    contentString += ".equ page_directory, __end_align_4k\n"
    contentString += ".equ page_table, __end_align_4k + 0x1000\n"
    contentString += ".equ page_directory_pointer_table, __end_align_4k + 0x2000\n"
    contentString += ".equ page_map_level_4, __end_align_4k + 0x3000\n"
    contentString += ".equ page_directory_1, __end_align_4k + 0x4000\n"
    contentString += ".macro SETUP_PAGING_4M\n"
    contentString += "    LOCAL page_setup_start page_setup_end\n"
    contentString += "    PUSH_EADX\n"
    contentString += "    /* Page directory steup. */\n"
    contentString += "    /* Set the top 20 address bits. */\n"
    contentString += "    mov $page_table, %eax\n"
    contentString += "    /* Zero out the 4 low flag bits of the second byte (top 20 are address). */\n"
    contentString += "    and $0xF000, %ax\n"
    contentString += "    mov %eax, page_directory\n"
    contentString += "    /* Set flags for the first byte. */\n"
    contentString += "    mov $0b00100111, %al\n"
    contentString += "    mov %al, page_directory\n"
    contentString += "    /* Page table setup. */\n"
    contentString += "    mov $0, %eax\n"
    contentString += "    mov $page_table, %ebx\n"
    contentString += "page_setup_start:\n"
    contentString += "    cmp $0x400, %eax\n"
    contentString += "    je page_setup_end\n"
    contentString += "    /* Top 20 address bits. */\n"
    contentString += "    mov %eax, %edx\n"
    contentString += "    shl $12, %edx\n"
    contentString += "    /*\n"
    contentString += "    Set flag bits 0-7. We only set to 1:\n"
    contentString += "    -   bit 0: Page present\n"
    contentString += "    -   bit 1: Page is writable.\n"
    contentString += "        Might work without this as the permission also depends on CR0.WP.\n"
    contentString += "    */\n"
    contentString += "    mov $0b00000011, %dl\n"
    contentString += "    /* Zero flag bits 8-11 */\n"
    contentString += "    and $0xF0, %dh\n"
    contentString += "    mov %edx, (%ebx)\n"
    contentString += "    inc %eax\n"
    contentString += "    add $4, %ebx\n"
    contentString += "    jmp page_setup_start\n"
    contentString += "page_setup_end:\n"
    contentString += "    POP_EDAX\n"
    contentString += ".endm\n"
    contentString += ".macro SETUP_PAGING_IA32E_1G\n"
    contentString += "    LOCAL page_setup_start, page_setup_end\n"
    contentString += "    PUSH_EADX\n"
    contentString += "    /* Settings for page table entries */\n"
    contentString += "    .equ pml4_flags, 0b011  /* 1 (writable), 0 (present) */\n"
    contentString += "    .equ pdpt_flags, 0b011  /* 1 (writable), 0 (present) */\n"
    contentString += "    .equ pd_flags, 0b110000011  /* bits 8 (global), 7 (page size), 1 (writable), 0 (present) */\n"
    contentString += "    /*.equ pd_flags, 0b110010011*/  /* FIXME: DO NOT USE THIS FOR EXPERIMENTS... bits 8 (global), 7 (page size), 4 (cache disabled), 1 (writable), 0 (present) */\n"
    contentString += "    /* NOTE: page_directory_1 maps to address 0xFEE00300, which is EFER register */\n"
    contentString += "    /* PML4: 0, PDPT: 11, PD: 111110111 */\n"
    contentString += "    /* Page map level 4 */\n"
    contentString += "    mov $page_directory_pointer_table, %edx\n"
    contentString += "    orl $pml4_flags, %edx\n"
    contentString += "    mov %edx, page_map_level_4\n"
    contentString += "    movl $0, page_map_level_4 + 0x4\n"
    contentString += "    /* Page directory pointer table */\n"
    contentString += "    mov $page_directory, %edx\n"
    contentString += "    orl $pdpt_flags, %edx\n"
    contentString += "    mov %edx, page_directory_pointer_table  /* [38:30]: 0b000000000 */\n"
    contentString += "    movl $0, page_directory_pointer_table + 0x4\n"
    contentString += "    mov $page_directory_1, %edx\n"
    contentString += "    orl $pdpt_flags, %edx\n"
    contentString += "    mov %edx, page_directory_pointer_table + (0b11 << 3)  /* [38:30]: 0b000000011 */\n"
    contentString += "    movl $0, page_directory_pointer_table + (0b11 << 3) + 0x4\n"
    contentString += "    /* Page directory table */\n"
    contentString += "    mov $0, %eax\n"
    contentString += "    mov $page_directory, %ebx\n"
    contentString += "page_setup_loop:\n"
    contentString += "    mov %eax, %edx\n"
    contentString += "    shl $21, %edx  /* 2MB page */\n"
    contentString += "    orl $pd_flags, %edx\n"
    contentString += "    mov %edx, (%ebx)\n"
    contentString += "    add $4, %ebx\n"
    contentString += "    movl $0x0, (%ebx)  /* Never gonna use > 4GB address space */\n"
    contentString += "    add $4, %ebx\n"
    contentString += "    inc %eax\n"
    contentString += "    cmp $0x200, %eax  /* 512 entries */\n"
    contentString += "    jl page_setup_loop\n"
    contentString += "    mov $0b11111110111 << 21, %edx\n"
    contentString += "    orl $pd_flags, %edx\n"
    contentString += "    mov $page_directory_1 + (0b111110111 << 3), %ebx\n"
    contentString += "    mov %edx, (%ebx)\n"
    contentString += "    add $4, %ebx\n"
    contentString += "    movl $0x0, (%ebx)\n"
    contentString += "    /* Page table: No need in 2MB-page table */\n"
    contentString += "    POP_EDAX\n"
    contentString += ".endm\n"
    contentString += ".macro PAGING_ON\n"
    contentString += "    /* Tell the CPU where the page directory is. */\n"
    contentString += "    mov $page_directory, %eax\n"
    contentString += "    mov %eax, %cr3\n"
    contentString += "    /* Turn paging on. */\n"
    contentString += "    mov %cr0, %eax\n"
    contentString += "    or $0x80000000, %eax\n"
    contentString += "    mov %eax, %cr0\n"
    contentString += ".endm\n"
    contentString += ".macro PAGING_IA32E_ON\n"
    contentString += "    /* disable old paging */\n"
    contentString += "    mov %cr0, %eax\n"
    contentString += "    and $0x7FFFFFFF, %eax\n"
    contentString += "    mov %eax, %cr0\n"
    contentString += "    /* Tell the CPU where the page directory is. */\n"
    contentString += "    mov $page_map_level_4, %eax\n"
    contentString += "    and $0xFFFFF000, %eax\n"
    contentString += "    mov %eax, %cr3\n"
    contentString += "    /* set PAE bit in CR4 */\n"
    contentString += "    mov %cr4, %eax\n"
    contentString += "    or $(1<<5), %eax\n"
    contentString += "    mov %eax, %cr4\n"
    contentString += "    /* set IA32_EFER.LME flag */\n"
    contentString += "    mov $0xC0000080, %ecx\n"
    contentString += "    rdmsr\n"
    contentString += "    or $(1<<8), %eax  /* bit 8 */\n"
    contentString += "    wrmsr\n"
    contentString += "    /* turn paging on */\n"
    contentString += "    mov %cr0, %eax\n"
    contentString += "    or $(1<<31), %eax\n"
    contentString += "    /*or $(0x3<<30), %eax */  /* FIXME: CACHE DISABLED... THIS IS ONLY FOR TESTING */\n"
    contentString += "    mov %eax, %cr0\n"
    contentString += ".endm\n"
    contentString += "/* Turn paging off. */\n"
    contentString += ".macro PAGING_OFF\n"
    contentString += "    mov %cr0, %eax\n"
    contentString += "    and $0x7FFFFFFF, %eax\n"
    contentString += "    mov  %eax, %cr0\n"
    contentString += ".endm\n"
    contentString += ".macro PAGING_IA32E_OFF\n"
    contentString += "    mov %cr0, %rax\n"
    contentString += "    and $0x7FFFFFFF, %eax\n"
    contentString += "    mov %rax, %cr0\n"
    contentString += ".endm\n"
    contentString += "/* IDT */\n"
    contentString += ".macro IDT_START\n"
    contentString += "    idt_start:\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_END\n"
    contentString += "idt_end:\n"
    contentString += "/* Exact same structure as gdt_descriptor. */\n"
    contentString += "idt_descriptor:\n"
    contentString += "    .word idt_end - idt_start\n"
    contentString += "    .long idt_start\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_START\n"
    contentString += "idt_ia32e_start:\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_END\n"
    contentString += "idt_ia32e_end:\n"
    contentString += "/* Exact same structure as gdt_descriptor. */\n"
    contentString += "idt_ia32e_descriptor:\n"
    contentString += "    /* .word idt_ia32e_end - idt_ia32e_start */\n"
    contentString += "    .word idt_ia32e_end - idt_ia32e_start - 1\n"
    contentString += "    .quad idt_ia32e_start\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_ENTRY\n"
    contentString += "    /*\n"
    contentString += "    Low handler address.\n"
    contentString += "    It is impossible to write:\n"
    contentString += "    .word (handler & 0x0000FFFF)\n"
    contentString += "    as we would like:\n"
    contentString += "    http://stackoverflow.com/questions/18495765/invalid-operands-for-binary-and\n"
    contentString += "    because this address has to be split up into two.\n"
    contentString += "    So this must be done at runtime.\n"
    contentString += "    Why this design choice from Intel?! Weird.\n"
    contentString += "    */\n"
    contentString += "    .word 0\n"
    contentString += "    /* Segment selector: byte offset into the GDT. */\n"
    contentString += "    .word CODE_SEG\n"
    contentString += "    /* Reserved 0. */\n"
    contentString += "    .byte 0\n"
    contentString += "    /*\n"
    contentString += "    Flags. Format:\n"
    contentString += "    - 1 bit: present. If 0 and this happens, triple fault.\n"
    contentString += "    - 2 bits: ring level we will be called from.\n"
    contentString += "    - 5 bits: fixed to 0xE.\n"
    contentString += "    */\n"
    contentString += "    .byte 0x8E\n"
    contentString += "    /* High word of base. */\n"
    contentString += "    .word 0\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_ENTRY\n"
    contentString += "    /* Offset 15:0 */\n"
    contentString += "    .word 0\n"
    contentString += "    /* Segment selector: byte offset into the GDT. */\n"
    contentString += "    .word CODE_SEG\n"
    contentString += "    /* Reserved 0. */\n"
    contentString += "    .byte 0\n"
    contentString += "    /*\n"
    contentString += "    Flags. Format:\n"
    contentString += "    - 1 bit: present. If 0 and this happens, triple fault.\n"
    contentString += "    - 2 bits: ring level we will be called from.\n"
    contentString += "    - 5 bits: fixed to 0xE.\n"
    contentString += "    */\n"
    contentString += "    .byte 0x8E\n"
    contentString += "    /* Offset 31:16 */\n"
    contentString += "    .word 0\n"
    contentString += "    /* Offset 63:32 */\n"
    contentString += "    .long 0\n"
    contentString += "    /* reserved 0 */\n"
    contentString += "    .long 0\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "- index: r/m/imm32 Index of the entry to setup.\n"
    contentString += "- handler: r/m/imm32 Address of the handler function.\n"
    contentString += "*/\n"
    contentString += ".macro IDT_SETUP_ENTRY index, handler\n"
    contentString += "    push %eax\n"
    contentString += "    push %edx\n"
    contentString += "    mov \\index, %eax\n"
    contentString += "    mov \\handler, %edx\n"
    contentString += "    mov %dx, idt_start(,%eax, 8)\n"
    contentString += "    shr $16, %edx\n"
    contentString += "    mov %dx, (idt_start + 6)(,%eax, 8)\n"
    contentString += "    pop %edx\n"
    contentString += "    pop %eax\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_SETUP_ENTRY index, handler\n"
    contentString += "    #push %eax\n"
    contentString += "    #push %edx\n"
    contentString += "    push %rax\n"
    contentString += "    push %rdx\n"
    contentString += "    mov \\index, %eax\n"
    contentString += "    mov \\handler, %edx\n"
    contentString += "    shl $4, %eax  # eax = eax * 16\n"
    contentString += "    mov %dx, idt_ia32e_start(%eax)\n"
    contentString += "    shr $16, %edx\n"
    contentString += "    mov %dx, (idt_ia32e_start + 6)(%eax)\n"
    contentString += "    #pop %edx\n"
    contentString += "    #pop %eax\n"
    contentString += "    pop %rdx\n"
    contentString += "    pop %rax\n"
    contentString += ".endm\n"
    contentString += "/* Shamelessly copied from James Molloy's tutorial. */\n"
    contentString += ".macro ISR_NOERRCODE i\n"
    contentString += "    isr\\()\\i:\n"
    contentString += "        cli\n"
    contentString += "        /*\n"
    contentString += "        Push a dummy 0 for interrupts that don't push any code.\n"
    contentString += "        http://stackoverflow.com/questions/10581224/why-does-iret-from-a-page-fault-handler-generate-interrupt-13-general-protectio/33398064#33398064\n"
    contentString += "        */\n"
    contentString += "        push $0\n"
    contentString += "        push $\i\n"
    contentString += "        jmp interrupt_handler_stub\n"
    contentString += ".endm\n"
    contentString += ".macro ISR_ERRCODE i\n"
    contentString += "    isr\\()\\i:\n"
    contentString += "        cli\n"
    contentString += "        push $\\i\n"
    contentString += "        jmp interrupt_handler_stub\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "Protected mode PIC IRQ numbers after remapping it.\n"
    contentString += "*/\n"
    contentString += "#define PIC_MASTER_ISR_NUMBER $0x20\n"
    contentString += "#define PIC_SLAVE_ISR_NUMBER $0x28\n"
    contentString += "#define IRQ_DE   $0x0\n"
    contentString += "#define IRQ_DB   $0x1\n"
    contentString += "#define IRQ_NMI  $0x2\n"
    contentString += "#define IRQ_BP   $0x3\n"
    contentString += "#define IRQ_OF   $0x4\n"
    contentString += "#define IRQ_BR   $0x5\n"
    contentString += "#define IRQ_UD   $0x6\n"
    contentString += "#define IRQ_NM   $0x7\n"
    contentString += "#define IRQ_DF   $0x8\n"
    contentString += "#define IRQ_TS   $0xA\n"
    contentString += "#define IRQ_NP   $0xB\n"
    contentString += "#define IRQ_SS   $0xC\n"
    contentString += "#define IRQ_GP   $0xD\n"
    contentString += "#define IRQ_PF   $0xE\n"
    contentString += "#define IRQ_MF   $0x10\n"
    contentString += "#define IRQ_AC   $0x11\n"
    contentString += "#define IRQ_MC   $0x12\n"
    contentString += "#define IRQ_XM   $0x13\n"
    contentString += "#define IRQ_VE   $0x14\n"
    contentString += "#define IRQ_PIT  $0x20\n"
    contentString += "#define IRQ_KBD  $0x21\n"
    contentString += "#define IRQ_COM2 $0x23\n"
    contentString += "#define IRQ_COM1 $0x24\n"
    contentString += "#define IRQ_LPT2 $0x25\n"
    contentString += "#define IRQ_FPY  $0x26\n"
    contentString += "#define IRQ_LPT1 $0x27\n"
    contentString += "#define IRQ_RTC  $0x28\n"
    contentString += "#define IRQ_PS2  $0x2C\n"
    contentString += "#define IRQ_COP  $0x2D\n"
    contentString += "#define IRQ_PATA $0x2E\n"
    contentString += "#define IRQ_SATA $0x2F\n"
    contentString += "/*\n"
    contentString += "Entries and handlers.\n"
    contentString += "48 = 32 processor built-ins + 16 PIC interrupts.\n"
    contentString += "In addition to including this, you should also call\n"
    contentString += "- call IDT_SETUP_48_ISRS to setup the handler addreses.\n"
    contentString += "- define an `interrupt_handler(uint32 number, uint32 error)` function\n"
    contentString += "*/\n"
    contentString += ".macro IDT_48_ENTRIES\n"
    contentString += "    /* IDT. */\n"
    contentString += "    IDT_START\n"
    contentString += "    #.rept 48\n"
    contentString += "    .rept 49\n"
    contentString += "    IDT_ENTRY\n"
    contentString += "    .endr\n"
    contentString += "    IDT_END\n"
    contentString += "    /* ISRs */\n"
    contentString += "    .irp i, 0, 1, 2, 3, 4, 5, 6, 7\n"
    contentString += "        ISR_NOERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    ISR_ERRCODE   8\n"
    contentString += "    ISR_NOERRCODE 9\n"
    contentString += "    .irp i, 10, 11, 12, 13, 14\n"
    contentString += "        ISR_ERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    .irp i, 15, 16, 17, 18, 19, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            30, 31, 32, 33, 34, 35, 36, 37, 38, 39, \\\n"
    contentString += "            40, 41, 42, 43, 44, 45, 46, 47, 48\n"
    contentString += "        ISR_NOERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    /* Factor out things which we will want to do in every handler. */\n"
    contentString += "    interrupt_handler_stub:\n"
    contentString += "        cli\n"
    contentString += "        call interrupt_handler\n"
    contentString += "        /* If we are a PIC interrupt (>=32), do an EOI. */\n"
    contentString += "        cmp PIC_MASTER_ISR_NUMBER, (%esp)\n"
    contentString += "        jb interrupt_handler_stub.noeoi\n"
    contentString += "        cmp PIC_SLAVE_ISR_NUMBER, (%esp)\n"
    contentString += "        jb interrupt_handler_stub.mastereoi\n"
    contentString += "        PIC_SLAVE_EOI\n"
    contentString += "    interrupt_handler_stub.mastereoi:\n"
    contentString += "        PIC_MASTER_EOI\n"
    contentString += "    interrupt_handler_stub.noeoi:\n"
    contentString += "        add $8, %esp\n"
    contentString += "        sti\n"
    contentString += "        iret\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_48_ENTRIES\n"
    contentString += "    /* IDT. */\n"
    contentString += "    IDT_IA32E_START\n"
    contentString += "    .rept 48\n"
    contentString += "    IDT_IA32E_ENTRY\n"
    contentString += "    .endr\n"
    contentString += "    IDT_IA32E_END\n"
    contentString += "    /* ISRs */\n"
    contentString += "    .irp i, 0, 1, 2, 3, 4, 5, 6, 7\n"
    contentString += "        ISR_NOERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    ISR_ERRCODE   8\n"
    contentString += "    ISR_NOERRCODE 9\n"
    contentString += "    .irp i, 10, 11, 12, 13, 14\n"
    contentString += "        ISR_ERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    .irp i, 15, 16, 17, 18, 19, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            30, 31, 32, 33, 34, 35, 36, 37, 38, 39, \\\n"
    contentString += "            40, 41, 42, 43, 44, 45, 46, 47\n"
    contentString += "        ISR_NOERRCODE \\i\n"
    contentString += "    .endr\n"
    contentString += "    /* Factor out things which we will want to do in every handler. */\n"
    contentString += "    interrupt_handler_stub:\n"
    contentString += "        cli\n"
    contentString += "        call interrupt_handler\n"
    contentString += "        /* If we are a PIC interrupt (>=32), do an EOI. */\n"
    contentString += "        cmp PIC_MASTER_ISR_NUMBER, (%esp)\n"
    contentString += "        jb interrupt_handler_stub.noeoi\n"
    contentString += "        cmp PIC_SLAVE_ISR_NUMBER, (%esp)\n"
    contentString += "        jb interrupt_handler_stub.mastereoi\n"
    contentString += "        PIC_SLAVE_EOI\n"
    contentString += "    interrupt_handler_stub.mastereoi:\n"
    contentString += "        PIC_MASTER_EOI\n"
    contentString += "    interrupt_handler_stub.noeoi:\n"
    contentString += "        #add $8, %esp\n"
    contentString += "        add $16, %esp\n"
    contentString += "        sti\n"
    contentString += "        #iret\n"
    contentString += "        iretq\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_SETUP_48_ISRS\n"
    contentString += "    .irp i,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, \\\n"
    contentString += "            10, 11, 12, 13, 14, 15, 16, 17, 18, 19, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            30, 31, 32, 33, 34, 35, 36, 37, 38, 39, \\\n"
    contentString += "            40, 41, 42, 43, 44, 45, 46, 47, 48\n"
    contentString += "        IDT_SETUP_ENTRY $\\i, $isr\\()\\i\n"
    contentString += "    .endr\n"
    contentString += "    lidt idt_descriptor\n"
    contentString += ".endm\n"
    contentString += ".macro IDT_IA32E_SETUP_48_ISRS\n"
    contentString += "    .irp i,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, \\\n"
    contentString += "            10, 11, 12, 13, 14, 15, 16, 17, 18, 19, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            20, 21, 22, 23, 24, 25, 26, 27, 28, 29, \\\n"
    contentString += "            30, 31, 32, 33, 34, 35, 36, 37, 38, 39, \\\n"
    contentString += "            40, 41, 42, 43, 44, 45, 46, 47\n"
    contentString += "        IDT_IA32E_SETUP_ENTRY $\\i, $isr\\()\\i\n"
    contentString += "    .endr\n"
    contentString += "    lidt idt_ia32e_descriptor\n"
    contentString += ".endm\n"
    contentString += "/* BIOS */\n"
    contentString += ".macro CURSOR_POSITION x=$0, y=$0\n"
    contentString += "    PUSH_ADX\n"
    contentString += "    mov $0x02, %ah\n"
    contentString += "    mov $0x00, %bh\n"
    contentString += "    mov \\x, %dh\n"
    contentString += "    mov \\y, %dl\n"
    contentString += "    int $0x10\n"
    contentString += "    POP_DAX\n"
    contentString += ".endm\n"
    contentString += "/* Clear the screen, move to position 0, 0. */\n"
    contentString += ".macro CLEAR\n"
    contentString += "    PUSH_ADX\n"
    contentString += "    mov $0x0600, %ax\n"
    contentString += "    mov $0x7, %bh\n"
    contentString += "    mov $0x0, %cx\n"
    contentString += "    mov $0x184f, %dx\n"
    contentString += "    int $0x10\n"
    contentString += "    CURSOR_POSITION\n"
    contentString += "    POP_DAX\n"
    contentString += ".endm\n"
    contentString += "/* VGA */\n"
    contentString += ".macro VGA_PRINT_STRING_64BIT s\n"
    contentString += "    LOCAL loop, end\n"
    contentString += "    PUSH_RADX\n"
    contentString += "    mov \\s, %ecx\n"
    contentString += "    mov vga_current_line, %eax\n"
    contentString += "    mov $0, %edx\n"
    contentString += "    /* Number of horizontal lines. */\n"
    contentString += "    mov $25, %ebx\n"
    contentString += "    div %ebx\n"
    contentString += "    mov %edx, %eax\n"
    contentString += "    /* 160 == 80 * 2 == line width * bytes per character on screen */\n"
    contentString += "    mov $160, %edx\n"
    contentString += "    mul %edx\n"
    contentString += "    /* 0xb8000 == magic video memory address which shows on the screen. */\n"
    contentString += "    lea 0xb8000(%eax), %edx\n"
    contentString += "    /* White on black. */\n"
    contentString += "    mov $0x0f, %ah\n"
    contentString += "loop:\n"
    contentString += "    mov (%ecx), %al\n"
    contentString += "    cmp $0, %al\n"
    contentString += "    je end\n"
    contentString += "    mov %ax, (%edx)\n"
    contentString += "    add $1, %ecx\n"
    contentString += "    add $2, %edx\n"
    contentString += "    jmp loop\n"
    contentString += "end:\n"
    contentString += "    incl vga_current_line\n"
    contentString += "    POP_RDAX\n"
    contentString += ".endm\n"
    contentString += ".macro VGA_PRINT_BYTES_64BIT s, n=$16\n"
    contentString += "    LOCAL end, loop\n"
    contentString += "    PUSH_RADX\n"
    contentString += "    push $0  # Null terminator\n"
    contentString += "    mov $0, %ebx\n"
    contentString += "loop:\n"
    contentString += "    mov \\s, %ecx\n"
    contentString += "    add %ebx, %ecx\n"
    contentString += "    mov (%ecx), %ecx\n"
    contentString += "    HEX <%cl>\n"
    contentString += "    mov %ax, %dx\n"
    contentString += "    shl $16, %rdx\n"
    contentString += "    HEX <%ch>\n"
    contentString += "    mov %ax, %dx\n"
    contentString += "    shl $16, %rdx\n"
    contentString += "    shr $16, %ecx\n"
    contentString += "    HEX <%cl>\n"
    contentString += "    mov %ax, %dx\n"
    contentString += "    shl $16, %rdx\n"
    contentString += "    HEX <%ch>\n"
    contentString += "    mov %ax, %dx\n"
    contentString += "    push %rdx\n"
    contentString += "    add $4, %ebx\n"
    contentString += "    cmp \\n, %ebx\n"
    contentString += "    jl loop\n"
    contentString += "    mov %esp, %edx\n"
    contentString += "    VGA_PRINT_STRING_64BIT <%edx>\n"
    contentString += "    mov \\n, %ebx\n"
    contentString += "    shl $1, %ebx\n"
    contentString += "    add $8, %ebx\n"
    contentString += "    add %ebx, %esp\n"
    contentString += "    POP_RDAX\n"
    contentString += ".endm\n"
    contentString += "/* IO ports. */\n"
    contentString += ".macro OUTB value, port\n"
    contentString += "    push %ax\n"
    contentString += "    mov \\value, %al\n"
    contentString += "    out %al, \\port\n"
    contentString += "    pop %ax\n"
    contentString += ".endm\n"
    contentString += "#define PORT_PIC_MASTER_CMD $0x20\n"
    contentString += "#define PORT_PIC_MASTER_DATA $0x21\n"
    contentString += "#define PORT_PIT_CHANNEL0 $0x40\n"
    contentString += "#define PORT_PIT_MODE $0x43\n"
    contentString += "#define PORT_PIC_SLAVE_CMD $0xA0\n"
    contentString += "#define PORT_PIC_SLAVE_DATA $0xA1\n"
    contentString += "/* PIC */\n"
    contentString += "#define PIC_CMD_RESET $0x20\n"
    contentString += "#define PIC_ICR_LOW_ADDRESS $0xFEE00300\n"
    contentString += "#define PIC_ICR_HIGH_ADDRESS $0xFEE00310\n"
    contentString += "/* EOI End Of Interrupt: PIC it will not fire again unless we reset it. */\n"
    contentString += ".macro PIC_MASTER_EOI\n"
    contentString += "    OUTB PIC_CMD_RESET, PORT_PIC_MASTER_CMD\n"
    contentString += ".endm\n"
    contentString += ".macro PIC_SLAVE_EOI\n"
    contentString += "    OUTB PIC_CMD_RESET, PORT_PIC_SLAVE_CMD\n"
    contentString += ".endm\n"
    contentString += ".macro REMAP_PIC_32\n"
    contentString += "    /*\n"
    contentString += "    Remap the PIC interrupts to start at 32.\n"
    contentString += "    TODO understand.\n"
    contentString += "    */\n"
    contentString += "    OUTB $0x11, PORT_PIC_MASTER_CMD\n"
    contentString += "    OUTB $0x11, PORT_PIC_SLAVE_CMD\n"
    contentString += "    OUTB $0x20, PORT_PIC_MASTER_DATA\n"
    contentString += "    OUTB $0x28, PORT_PIC_SLAVE_DATA\n"
    contentString += "    OUTB $0x04, PORT_PIC_MASTER_DATA\n"
    contentString += "    OUTB $0x02, PORT_PIC_SLAVE_DATA\n"
    contentString += "    OUTB $0x01, PORT_PIC_MASTER_DATA\n"
    contentString += "    OUTB $0x01, PORT_PIC_SLAVE_DATA\n"
    contentString += "    OUTB $0x00, PORT_PIC_MASTER_DATA\n"
    contentString += "    OUTB $0x00, PORT_PIC_SLAVE_DATA\n"
    contentString += ".endm\n"
    contentString += ".macro MASK_MASTER_PIC irq\n"
    contentString += "    in PORT_PIC_MASTER_DATA, %al\n"
    contentString += "    or $(1 << \\irq), %al\n"
    contentString += "    out %al, PORT_PIC_MASTER_DATA\n"
    contentString += ".endm\n"
    contentString += ".macro MASK_SLAVE_PIC irq\n"
    contentString += "    in PORT_PIC_SLAVE_DATA, %al\n"
    contentString += "    or $(1 << \\irq), %al\n"
    contentString += "    out %al, PORT_PIC_SLAVE_DATA\n"
    contentString += ".endm\n"
    contentString += "/* PIT */\n"
    contentString += "#define PIT_FREQ 0x1234DD\n"
    contentString += "/*\n"
    contentString += "Set the minimum possible PIT frequency = 0x1234DD / 0xFFFF =~ 18.2 Hz\n"
    contentString += "This is a human friendly frequency: you can see individual events,\n"
    contentString += "but you don't have to wait much for each one.\n"
    contentString += "*/\n"
    contentString += ".macro PIT_SET_MIN_FREQ\n"
    contentString += "    push %eax\n"
    contentString += "    mov $0xFF, %al\n"
    contentString += "    out %al, PORT_PIT_CHANNEL0\n"
    contentString += "    out %al, PORT_PIT_CHANNEL0\n"
    contentString += "    pop %eax\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "We have to split the 2 ax bytes,\n"
    contentString += "as we can only communicate one byte at a time here.\n"
    contentString += "- freq: 16 bit compile time constant desired frequency.\n"
    contentString += "        Range: 19 - 0x1234DD.\n"
    contentString += "*/\n"
    contentString += ".macro PIT_SET_FREQ freq\n"
    contentString += "    #push %eax\n"
    contentString += "    push %rax\n"
    contentString += "    mov $(PIT_FREQ / \\freq), %ax\n"
    contentString += "    out %al, PORT_PIT_CHANNEL0\n"
    contentString += "    mov %ah, %al\n"
    contentString += "    out %al, PORT_PIT_CHANNEL0\n"
    contentString += "    #pop %eax\n"
    contentString += "    pop %rax\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "Sleep for `ticks` ticks of the PIT at current frequency.\n"
    contentString += "PIT_SLEEP_HANDLER_UPDATE must be placed in the PIT handler for this to work.\n"
    contentString += "Currently only one can be used at a given time.\n"
    contentString += "*/\n"
    contentString += ".macro PIT_SLEEP_TICKS ticks\n"
    contentString += "    LOCAL loop\n"
    contentString += "    movb $1, pit_sleep_ticks_locked\n"
    contentString += "    movl \\ticks, pit_sleep_ticks_count\n"
    contentString += "    jmp loop\n"
    contentString += "loop:\n"
    contentString += "    cmpb $0, pit_sleep_ticks_locked\n"
    contentString += "    jne loop\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "Must be placed in the PIT handler for PIT_SLEEP_TICKS to work.\n"
    contentString += "*/\n"
    contentString += ".macro PIT_SLEEP_TICKS_HANDLER_UPDATE\n"
    contentString += "    LOCAL dont_unlock\n"
    contentString += "    decl pit_sleep_ticks_count\n"
    contentString += "    cmpl $0, pit_sleep_ticks_count\n"
    contentString += "    jne dont_unlock\n"
    contentString += "    movb $0, pit_sleep_ticks_locked\n"
    contentString += "dont_unlock:\n"
    contentString += ".endm\n"
    contentString += ".macro PIT_SLEEP_TICKS_GLOBALS\n"
    contentString += "pit_sleep_ticks_count:\n"
    contentString += "    .long 0\n"
    contentString += "pit_sleep_ticks_locked:\n"
    contentString += "    .byte 0\n"
    contentString += ".endm\n"
    contentString += "/*\n"
    contentString += "Define the properties of the wave:\n"
    contentString += "- Channel: 0\n"
    contentString += "- access mode: lobyte/hibyte\n"
    contentString += "- operating mode: rate generator\n"
    contentString += "- BCD/binary: binary\n"
    contentString += "*/\n"
    contentString += ".macro PIT_GENERATE_FREQUENCY\n"
    contentString += "    OUTB $0b00110100, PORT_PIT_MODE\n"
    contentString += ".endm\n"
    contentString += "/* IVT */\n"
    contentString += "#define IVT_PIT 8\n"
    contentString += "#define IVT_HANDLER_SIZE 4\n"
    contentString += "#define IVT_CODE_OFFSET 2\n"
    contentString += "/* Setup interrupt handler 8: this is where the PIC maps IRQ 0 to. */\n"
    contentString += ".macro IVT_PIT_SETUP\n"
    contentString += "    movw $handler, IVT_PIT * IVT_HANDLER_SIZE\n"
    contentString += "    mov %cs, IVT_PIT * IVT_HANDLER_SIZE + IVT_CODE_OFFSET\n"
    contentString += ".endm\n"
    contentString += "/* Activate A20 */\n"
    contentString += ".macro ACTIVATE_A20_BIOS\n"
    contentString += "    # http://wiki.osdev.org/A20_Line\n"
    contentString += "    # INT 0x15 AX=0x2400: disable A20\n"
    contentString += "    # INT 0x15 AX=0x2401: enable A20\n"
    contentString += "    # INT 0x15 AX=0x2402: query status A20\n"
    contentString += "    # INT 0x15 AX=0x2403: query A20 support\n"
    contentString += "    # NOTE: Call this macro before entering protected mode\n"
    contentString += "    # Unfortunately, DELL Optiplex 755 (with Intel Q6600) does not support this in its BIOS\n"
    contentString += "    LOCAL a20_notsupported, a20_failed, a20_activated\n"
    contentString += "    # Check if A20 is supported\n"
    contentString += "    mov $0x2403, %ax\n"
    contentString += "    int $0x15\n"
    contentString += "    jb a20_notsupported\n"
    contentString += "    cmp $0, %ah\n"
    contentString += "    jnz a20_notsupported\n"
    contentString += "    # Check if A20 is already activated\n"
    contentString += "    mov $0x2402, %ax\n"
    contentString += "    int $0x15\n"
    contentString += "    jb a20_failed\n"
    contentString += "    cmp $0, %ah\n"
    contentString += "    jnz a20_failed\n"
    contentString += "    cmp $1, %al\n"
    contentString += "    jz a20_activated\n"
    contentString += "    # Activate A20\n"
    contentString += "    mov $0x2401, %ax\n"
    contentString += "    int $0x15\n"
    contentString += "    jb a20_failed\n"
    contentString += "    cmp $0, %ah\n"
    contentString += "    jnz a20_failed\n"
    contentString += "a20_notsupported:\n"
    contentString += "    mov $0x2, %ax\n"
    contentString += "    jmp a20_done\n"
    contentString += "a20_failed:\n"
    contentString += "    mov $0x1, %ax\n"
    contentString += "    jmp a20_done\n"
    contentString += "a20_activated:\n"
    contentString += "    mov $0x0, %ax\n"
    contentString += "a20_done:\n"
    contentString += ".endm\n"
    contentString += ".macro ACTIVATE_A20_KBD\n"
    contentString += "    # http://wiki.osdev.org/A20_Line\n"
    contentString += "    # NOTE: Call this macro before entering protected mode\n"
    contentString += "    # This method works in DELL Optiplex 755 (with Intel Q6600)\n"
    contentString += "    LOCAL a20_wait, a20_done\n"
    contentString += "    cli\n"
    contentString += "    call a20_wait\n"
    contentString += "    mov $0xAD, %al\n"
    contentString += "    out %al, $0x64\n"
    contentString += "    call a20_wait\n"
    contentString += "    mov $0xD0, %al\n"
    contentString += "    out %al, $0x64\n"
    contentString += "    call a20_wait\n"
    contentString += "    in $0x60, %al\n"
    contentString += "    push %ax\n"
    contentString += "    call a20_wait\n"
    contentString += "    mov $0xD1, %al\n"
    contentString += "    out %al, $0x64\n"
    contentString += "    call a20_wait\n"
    contentString += "    pop %ax\n"
    contentString += "    or $0x2, %al\n"
    contentString += "    out %al, $0x60\n"
    contentString += "    call a20_wait\n"
    contentString += "    mov $0xAE, %al\n"
    contentString += "    out %al, $0x64\n"
    contentString += "    call a20_wait\n"
    contentString += "    sti\n"
    contentString += "    jmp a20_done\n"
    contentString += "a20_wait:\n"
    contentString += "    in $0x64, %al\n"
    contentString += "    test $0x2, %al\n"
    contentString += "    jnz a20_wait\n"
    contentString += "    ret\n"
    contentString += "a20_done:\n"
    contentString += ".endm\n"

    commonFileFP = open(filePath, "w")
    commonFileFP.write(contentString)
    commonFileFP.close()

def hash_x86(filePath, headerFileName):
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

def manager_x86(managerFileName, headerName, threadList, signatureSize, regBitWidth, numCores, strideType):
    managerString  = ""
    managerString += "/* Some code is adopted from paging.S & smp.S in x86 bare-metal programming examples */\n"
    managerString += "/* https://github.com/cirosantilli/x86-bare-metal-examples */\n"
    managerString += "#include \"%s\"\n" % headerName
    managerString += "#include \"common.h\"\n"
    managerString += "    .globl classify_result_binary\n"
    managerString += "BEGIN\n"
    managerString += "    CLEAR\n"
    managerString += "    STAGE2_LBA\n"
    managerString += "    ACTIVATE_A20_KBD\n"
    managerString += "    cli\n"
    managerString += "    PROTECTED_MODE\n"
    managerString += "    SETUP_PAGING_IA32E_1G\n"
    managerString += "    PAGING_IA32E_ON\n"
    managerString += "    ENTER_64BIT_MODE\n"
    managerString += "    IDT_IA32E_SETUP_48_ISRS\n"
    managerString += "    REMAP_PIC_32\n"
    managerString += "    PIT_GENERATE_FREQUENCY\n"
    managerString += "    PIT_SET_FREQ 50000  /* Real machine: Each tick is 20us. */\n"
    managerString += "    #PIT_SET_FREQ 5000  /* QEMU: Each tick is 200us. */\n"
    managerString += "    sti\n"
    managerString += "    movb $0, thread_spawn_lock\n"
    managerString += "    movb $0, thread_join_lock\n"
    managerString += "    movb $0, TEMP_DATA0\n"
    managerString += "#ifdef EXEC_SYNC\n"
    managerString += "    movb $0, thread_exec_barrier0\n"
    managerString += "    movb $0, thread_exec_barrier1\n"
    managerString += "    movb $0, thread_exec_barrier_ptr\n"
    managerString += "#endif\n"
    managerString += "    /* Copy thread code */\n"
    managerString += "    cld\n"
    #for thread in threadList:
    #    managerString += "    mov $thread%d_length, %%ecx\n" % thread
    #    managerString += "    mov $thread%d_routine, %%esi\n" % thread
    #    managerString += "    mov $TEST_THREAD_BASE_%d, %%edi\n" % thread
    #    managerString += "    rep movsb\n"
    managerString += "    /* Create test data section */\n"
    managerString += "    mov $0x0, %ecx\n"
    managerString += "    mov $0xFFFF0000, %ebx\n"
    managerString += "    mov $TEST_DATA_SECTION, %edi\n"
    managerString += "init_data_section:\n"
    managerString += "    lea (%ebx,%ecx,1), %eax\n"
    managerString += "    mov %eax, (%edi)\n"
    if (strideType == 0):
        managerString += "    add $0x4, %edi  // strideType = 0\n"
    elif (strideType == 1):
        managerString += "    add $0x10, %edi  // strideType = 1\n"
    elif (strideType == 2):
        managerString += "    add $0x40, %edi  // strideType = 2\n"
    else:
        assert(False)
    managerString += "    inc %ecx\n"
    #managerString += "    cmp $TEST_DATA_LOCATIONS,%ecx\n"
    managerString += "    cmp $NUM_SHARED_DATA,%ecx\n"
    managerString += "    jl init_data_section\n"
    managerString += "    /* Initialize test BSS section */\n"
    managerString += "    mov $0x0, %edx\n"
    managerString += "    mov $TEST_BSS_SECTION, %edi\n"
    managerString += "init_bss_section:\n"
    managerString += "    mov $0x00000000, %edx\n"
    managerString += "    mov %edx, (%edi)\n"
    managerString += "    add $0x4, %edi\n"
    managerString += "    cmp $TEST_BSS_SECTION + TEST_BSS_SIZE_PER_THREAD * NUM_THREADS, %edi\n"
    managerString += "    jl init_bss_section\n"
    managerString += "    /* Load address of ICR low dword into ESI. */\n"
    managerString += "    mov PIC_ICR_LOW_ADDRESS, %esi\n"
    managerString += "    /* Broadcast INIT IPI to all APs */\n"
    managerString += "    mov $0x000C4500, %eax\n"
    managerString += "    /* Broadcast INIT IPI to all APs */\n"
    managerString += "    mov %eax, (%esi)\n"
    managerString += "    /* 10-millisecond delay loop. */\n"
    managerString += "    PIT_SLEEP_TICKS $500\n"
    managerString += "    movl $0x11111111, TEMP_DATA0\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $4\n"
    # Reversed-order core allocation (thread 0 -> core 3, thread 1 -> core 2, ... thread 3 -> core 0)
    managerString += "    # Assume core 0 is boot-strap processor\n"
    threadIdx = 0
    for thread in threadList:
        if thread == (numCores-1):
            continue
        managerString += "    # THREAD %d\n" % thread
        managerString += "    mov $0x%02d000000, %%eax\n" % ((numCores-1) - threadIdx)
        managerString += "    mov PIC_ICR_HIGH_ADDRESS, %esi\n"
        managerString += "    mov %eax, (%esi)\n"
        managerString += "    mov $thread%d_routine, %%eax\n" % thread
        managerString += "    shr $12, %eax\n"
        managerString += "    and $0xFF, %eax\n"
        managerString += "    or $0x00004600, %eax\n"
        #managerString += "    mov $0x00004600 + (thread%d_routine / 0x1000), %%eax\n" % thread
        managerString += "    mov PIC_ICR_LOW_ADDRESS, %esi\n"
        managerString += "    mov %eax, (%esi)\n"
        managerString += "    PIT_SLEEP_TICKS $10\n"
        managerString += "    mov %eax, (%esi)\n"
        threadIdx += 1
    managerString += "    movl $0x22222222, TEMP_DATA0\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $4\n"
    if thread == (numCores-1):
        managerString += "    # Primary core runs the last thread if no secondary core is available\n"
        managerString += "    jmp thread%d_routine\n" % thread
        # "wait_for_test_threads" is the return point
        managerString += "    .globl wait_for_test_threads\n"
    managerString += "wait_for_test_threads:\n"
    managerString += "    cmpb $NUM_THREADS, thread_join_lock\n"
    managerString += "    jne wait_for_test_threads\n"
    managerString += "    movl $0x33333333, TEMP_DATA0\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $4\n"
    #managerString += "#\n"
    #managerString += "# Construct linear hash table\n"
    #managerString += "#\n"
    #managerString += "# Register usage\n"
    #managerString += "#  -0x4(%ebp): current execution count\n"
    #managerString += "#  -0x8(%ebp): hash table size (number of hash key)\n"
    #managerString += "#  -0xC(%ebp): current index in hash table \n"
    #managerString += "#  eax: current signature from bss section\n"
    #managerString += "#  ebx:\n"
    #managerString += "#  ch: current thread count\n"
    #managerString += "#  cl: current sub-signature count\n"
    #managerString += "#  edx/rdx: temporary data\n"
    #managerString += "#  esi: address in bss section or in hash table\n"
    #managerString += "#  edi: second address\n"
    #managerString += "#  r10d: temporary\n"
    #managerString += "#  r11d: temporary\n"
    #managerString += "#\n"
    #managerString += "create_hash_table:\n"
    #managerString += "    push $0x0   /* -0x4(%ebp) both 32-bit and 64-bit */\n"
    #managerString += "    push $0x0   /* -0x8(%ebp) both 32-bit and 64-bit */\n"
    #managerString += "    push $0x0   /* -0xC(%ebp) both 32-bit and 64-bit */\n"
    #managerString += "execution_loop:\n"
    #managerString += "    movl $0x0, -0xC(%ebp)\n"
    #managerString += "hash_search_loop:\n"
    #managerString += "    movl -0xC(%ebp), %edx\n"
    #managerString += "    cmp -0x8(%ebp), %edx\n"
    #managerString += "    jge hash_entry_notfound  # jump if -0xC(%ebp) >= -0x8(%ebp)\n"
    #managerString += "    mov $0x0, %ch\n"
    #managerString += "1: # thread_loop\n"
    #managerString += "    mov $0x0, %cl\n"
    #managerString += "2: # signature-word loop\n"
    #managerString += "    ## Get value from bss section\n"
    #managerString += "    mov $TEST_BSS_SECTION, %esi\n"
    #managerString += "    mov -0x4(%ebp), %edx\n"
    #managerString += "    # %%esi <= %%esi + %%edx * %d\n" % signatureSize
    #for i in range(0, signatureSize, regBitWidth / 8):
    #    managerString += "    lea (%%esi,%%edx,%d), %%esi\n" % (regBitWidth / 8)
    #managerString += "    movzx %cl, %edx\n"
    #managerString += "    lea (%%esi,%%edx,%d), %%esi\n" % (regBitWidth / 8)
    #managerString += "    movzx %ch, %eax\n"
    #managerString += "    mov $TEST_BSS_SIZE_PER_THREAD, %edx\n"
    #managerString += "    mull %edx\n"
    #managerString += "    add %eax, %esi\n"
    #managerString += "    ## Get value from hash key table\n"
    #managerString += "    mov $TEST_HASH_KEY_TABLE, %edi\n"
    #managerString += "    mov -0xC(%ebp), %eax\n"
    #managerString += "    shll $%d, %%eax\n" % (int(math.ceil(math.log(signatureSize * len(threadList),2))))
    #managerString += "    add %eax, %edi\n"
    #managerString += "    movzx %cl, %edx\n"
    #managerString += "    lea (%%edi,%%edx,%d), %%edi\n" % (regBitWidth / 8)
    #managerString += "    movzx %ch, %edx\n"
    #managerString += "    # %%edi <= %%edi + %%edx * %d\n" % signatureSize
    #for i in range(0, signatureSize, regBitWidth / 8):
    #    managerString += "    lea (%%edi,%%edx,%d), %%edi\n" % (regBitWidth / 8)
    #managerString += "    # Compare\n"
    #managerString += "    mov (%edi), %rdx\n"
    #managerString += "    cmp %rdx, (%esi)\n"
    #managerString += "    jne move_next_hash\n"
    #managerString += "    inc %cl\n"
    #managerString += "    cmp $SIGNATURE_SIZE_IN_WORD, %cl  # subsignature count\n"
    #managerString += "    jl 2b\n"
    #managerString += "    inc %ch\n"
    #managerString += "    cmp $NUM_THREADS, %ch  # thread count\n"
    #managerString += "    jl 1b\n"
    #managerString += "    # Fall through\n"
    #managerString += "hash_entry_found:\n"
    #managerString += "    # Increase the hash value by 1\n"
    #managerString += "    mov $TEST_HASH_VALUE_TABLE, %esi\n"
    #managerString += "    movl -0xC(%ebp), %edx\n"
    #managerString += "    lea (%esi,%edx,4), %esi\n"
    #managerString += "    incl (%esi)\n"
    #managerString += "    jmp move_next_execution\n"
    #managerString += "move_next_hash:\n"
    #managerString += "    incl -0xC(%ebp)\n"
    #managerString += "    jmp hash_search_loop\n"
    #managerString += "hash_entry_notfound:\n"
    #managerString += "    ## Create a hash value entry (with value 1)\n"
    #managerString += "    mov $TEST_HASH_VALUE_TABLE, %esi\n"
    #managerString += "    movl -0x8(%ebp), %edx\n"
    #managerString += "    lea (%esi,%edx,4), %esi\n"
    #managerString += "    movl $1, (%esi)\n"
    #managerString += "    ## Create an hash key entry\n"
    #managerString += "    mov $0x0, %ch\n"
    #managerString += "1: # thread loop\n"
    #managerString += "    mov $0x0, %cl\n"
    #managerString += "2: # signature-word loop\n"
    #managerString += "    mov $TEST_BSS_SECTION, %edi\n"
    #managerString += "    mov -0x4(%ebp), %edx\n"
    #managerString += "    # %%edi <= %%edi + %%edx * %d\n" % signatureSize
    #for i in range(0, signatureSize, regBitWidth / 8):
    #    managerString += "    lea (%%edi,%%edx,%d), %%edi\n" % (regBitWidth / 8)
    #managerString += "    movzx %cl, %edx\n" 
    #managerString += "    lea (%%edi,%%edx,%d), %%edi\n" % (regBitWidth / 8)
    #managerString += "    movzx %ch, %eax\n"
    #managerString += "    mov $TEST_BSS_SIZE_PER_THREAD, %edx\n"
    #managerString += "    mull %edx\n"
    #managerString += "    add %eax, %edi\n"
    #managerString += "    mov $TEST_HASH_KEY_TABLE, %esi\n"
    #managerString += "    mov -0x8(%ebp), %eax\n"
    #managerString += "    shll $%d, %%eax\n" % (int(math.ceil(math.log(signatureSize * len(threadList),2))))
    #managerString += "    add %eax, %esi\n"
    #managerString += "    movzx %cl, %edx\n"
    #managerString += "    lea (%%esi,%%edx,%d), %%esi\n" % (regBitWidth / 8)
    #managerString += "    movzx %ch, %edx\n"
    #managerString += "    # %%esi <= %%esi + %%edx * %d\n" % signatureSize
    #for i in range(0, signatureSize, regBitWidth / 8):
    #    managerString += "    lea (%%esi,%%edx,%d), %%esi\n" % (regBitWidth / 8)
    #managerString += "    # Copy value from (%edi) to (%esi)\n"
    #managerString += "    mov (%edi), %rdx\n"
    #managerString += "    mov %rdx, (%esi)\n"
    #managerString += "    inc %cl\n"
    #managerString += "    cmp $SIGNATURE_SIZE_IN_WORD, %cl  # subsignature count\n"
    #managerString += "    jl 2b\n"
    #managerString += "    inc %ch\n"
    #managerString += "    cmp $NUM_THREADS, %ch  # thread count\n"
    #managerString += "    jl 1b\n"
    #managerString += "    incl -0x8(%ebp)\n"
    #managerString += "    # Fall through\n"
    #managerString += "    # END of hash_entry_not_found\n"
    #managerString += "move_next_execution:\n"
    #managerString += "    incl -0x4(%ebp)\n"
    #managerString += "    cmpl $EXECUTION_COUNT, -0x4(%ebp)\n"
    #managerString += "    jl execution_loop\n"
    #managerString += "print_result:\n"
    #managerString += "    mov -0x4(%ebp), %edx\n"
    #managerString += "    mov %edx, TEMP_DATA0\n"
    #managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $4\n"
    #managerString += "    mov -0x8(%ebp), %edx\n"
    #managerString += "    mov %edx, TEMP_DATA0\n"
    #managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $4\n"
    ##for i in range(4):
    ##    managerString += "    VGA_PRINT_BYTES_64BIT $(TEST_HASH_KEY_TABLE + 32 * %d), $32\n" % i
    #managerString += "    VGA_PRINT_BYTES_64BIT $TEST_HASH_VALUE_TABLE, $32\n"
    #managerString += "    addl $0x18, %esp  /* 64-bit */\n"
    #managerString += "    # End of create_hash_table\n"
    managerString += "\n"
    for threadIdx in range(len(threadList)):
        managerString += "    VGA_PRINT_BYTES_64BIT $(TEST_BSS_SECTION + TEST_BSS_SIZE_PER_THREAD * %d), $32\n" % threadIdx
    managerString += "\n"
    managerString += "    mov $TEST_HASH_STACK_BASE, %esp\n"
    managerString += "    call classify_result_binary\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $(result_addr+16), $4\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $(result_addr+24), $4\n"
    managerString += "\n"
    managerString += "    # Infinite loop\n"
    managerString += "    jmp .\n"
    managerString += "PIT_SLEEP_TICKS_GLOBALS\n"
    managerString += "IDT_IA32E_48_ENTRIES\n"
    managerString += "interrupt_handler:\n"
    managerString += "    cmp IRQ_PIT, 8(%rsp)\n"
    managerString += "    jne not_pit\n"
    managerString += "    PIT_SLEEP_TICKS_HANDLER_UPDATE\n"
    managerString += "    ret\n"
    managerString += "not_pit:\n"
    managerString += "    mov 8(%rsp), %rax\n"
    managerString += "    mov %rax, TEMP_DATA0\n"
    managerString += "    VGA_PRINT_BYTES_64BIT $TEMP_DATA0, $8\n"
    managerString += "    ret\n"

    managerFP = open(managerFileName, "w")
    managerFP.write(managerString)
    managerFP.close()
