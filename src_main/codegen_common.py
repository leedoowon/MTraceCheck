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
# This file should be called from codegen.py
#

####################################################################
# Data section
####################################################################
def generate_data_section(dataName, memLocs, strideType):
    assert(memLocs <= 0x10000)
    #dataArray = []
    #for i in range(memLocs):
    #    data = [i & 0xFF, (i >> 8) & 0xFF, 0xFF, 0xFF]
    #    dataArray += data
    ## Data contents will be initialized in test manager, so just create a placeholder
    if (strideType == 0):
        dataArray = [0xFF for i in range(memLocs * 4 * 1)]
    elif (strideType == 1):
        dataArray = [0xFF for i in range(memLocs * 4 * 4)]
    elif (strideType == 2):
        dataArray = [0xFF for i in range(memLocs * 4 * 16)]
    else:
        assert(False)
    dataFP = open(dataName, "w")
    dataFP.write(bytearray(dataArray))
    dataFP.close()


####################################################################
# BSS section (section to be written by test threads)
####################################################################
def generate_bss_section(bssName, bssSize):
    #bssArray = []
    #for i in range(bssSize):
    #    bssArray += [0x00]
    #bssFP = open(bssName, "w")
    #bssFP.write(bytearray(bssArray))
    #bssFP.close()
    # Faster code
    bssFP = open(bssName, "wb")
    bssFP.seek(bssSize-1)
    bssFP.write("\0")
    bssFP.close()


####################################################################
# Test manager CPP file
####################################################################
def generate_test_manager(cppName, headerName, threadList, bssBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, strideType):
    # See an example of cpp file at exp/160815_test_manager/test_manager.cpp
    # (This example is possibly outdated)
    wordTypeString = "uint%d_t" % regBitWidth
    cppString = ""
    cppString += "#include <stdio.h>\n"
    cppString += "#include <stdlib.h>\n"
    cppString += "#include <stdint.h>\n"
    cppString += "#include <pthread.h>\n"
    cppString += "#include <map>\n"
    cppString += "#include <vector>\n"
    cppString += "#include \"%s\"\n" % headerName
    for thread in threadList:
        cppString += "extern \"C\" void* thread%d_routine(void*);\n" % thread
    cppString += "volatile int thread_spawn_lock = 0;\n"
    cppString += "#ifdef EXEC_SYNC\n"
    cppString += "volatile int thread_exec_barrier0 = 0;\n"
    cppString += "volatile int thread_exec_barrier1 = 0;\n"
    cppString += "volatile int thread_exec_barrier_ptr = 0;\n"
    cppString += "#endif\n"
    cppString += "int main()\n"
    cppString += "{\n"
    cppString += "    int pthread_return;\n"
    cppString += "    int numThreads = %d;\n" % len(threadList)
    cppString += "    // Test BSS section initialization\n"
    cppString += "    %s *bss_address = (%s *) TEST_BSS_SECTION;\n" % (wordTypeString, wordTypeString)
    cppString += "    for (int i = 0; i < numThreads * TEST_BSS_SIZE_PER_THREAD; i += sizeof(%s)) {\n" % (wordTypeString)
    cppString += "        *(bss_address++) = 0;\n"
    cppString += "    }\n"
    cppString += "    // Test data section initialization\n"
    cppString += "    uint32_t *data_address= (uint32_t *) TEST_DATA_SECTION;\n"
    cppString += "    for (int i = 0; i < NUM_SHARED_DATA; i++) {\n"
    cppString += "        *data_address = (uint32_t) (0xFFFF0000 | i);\n"
    if (strideType == 0):
        cppString += "        data_address++;  // strideType = 0\n"
    elif (strideType == 1):
        cppString += "        data_address+=4;  // strideType = 1\n"
    elif (strideType == 2):
        cppString += "        data_address+=16;  // strideType = 2\n"
    else:
        assert(False)
    cppString += "    }\n"
    cppString += "    pthread_t* threads = (pthread_t *) malloc(sizeof(pthread_t) * numThreads);\n"
    for threadIndex in range(len(threadList)):
        cppString += "    pthread_return = pthread_create(&threads[%d], NULL, thread%d_routine, NULL);\n" % (threadIndex, threadList[threadIndex])
    cppString += "    for (int t = 0; t < numThreads; t++)\n"
    cppString += "        pthread_return = pthread_join(threads[t], NULL);\n"
    cppString += "    std::map<std::vector<%s>, int> signatureMap;\n" % (wordTypeString)
    cppString += "    std::vector<%s> resultVector;\n" % (wordTypeString)
    cppString += "    %s *signature = (%s *) TEST_BSS_SECTION;\n" % (wordTypeString, wordTypeString)
    cppString += "    for (int i = 0; i < EXECUTION_COUNT; i++) {\n"
    cppString += "        resultVector.clear();\n"
    #cppString += "#ifndef NO_PRINT\n"
    cppString += "#if 0\n"
    cppString += "        printf(\"%8d:\", i);\n"
    cppString += "#endif\n"
    cppString += "        for (int t = 0; t < numThreads; t++) {\n"
    cppString += "            for (int w = 0; w < SIGNATURE_SIZE_IN_WORD; w++) {\n"
    # NOTE: SIGNATURE WORD REORDERING
    #cppString += "        for (int w = SIGNATURE_SIZE_IN_WORD - 1; w >= 0; w--) {\n"
    #cppString += "            for (int t = 0; t < numThreads; t++) {\n"
    cppString += "                %s address = (%s) signature + t * TEST_BSS_SIZE_PER_THREAD + w * sizeof(%s);\n" % (wordTypeString, wordTypeString, wordTypeString)
    cppString += "                %s result = (%s)*(%s*)address;\n" % (wordTypeString, wordTypeString, wordTypeString)
    cppString += "                resultVector.push_back(result);\n"
    #cppString += "#ifndef NO_PRINT\n"
    cppString += "#if 0\n"
    cppString += "                printf(\" 0x%%0%dlx\", result);\n" % (regBitWidth / 8 * 2)
    #cppString += "                printf(\" 0x%%lx 0x%%0%dlx\", address, result);\n" % signatureSize
    cppString += "#endif\n"
    cppString += "            }\n"
    cppString += "        }\n"
    cppString += "        if (signatureMap.find(resultVector) == signatureMap.end())\n"
    cppString += "            signatureMap[resultVector] = 1;\n"
    cppString += "        else\n"
    cppString += "            signatureMap[resultVector]++;\n"
    #cppString += "#ifndef NO_PRINT\n"
    cppString += "#if 0\n"
    cppString += "        printf(\"\\n\");\n"
    cppString += "#endif\n"
    cppString += "        signature += SIGNATURE_SIZE_IN_WORD;\n"
    cppString += "    }\n"
    cppString += "#ifndef NO_PRINT\n"
    cppString += "    for (std::map<std::vector<%s>, int>::iterator it = signatureMap.begin(); it != signatureMap.end(); it++) {\n" % (wordTypeString)
    cppString += "        for (int i = 0; i < (it->first).size(); i++)\n"
    cppString += "            printf(\" 0x%%0%dlx\", (it->first)[i]);\n" % (regBitWidth / 8 * 2)
    cppString += "        printf(\": %d\\n\", it->second);\n"
    cppString += "    }\n"
    cppString += "#endif\n"
    cppString += "    printf(\"Number of unique results %lu out of %d\\n\", signatureMap.size(), EXECUTION_COUNT);\n"
    cppString += "    fflush(stdout);\n"
    cppString += "    return 0;\n"
    cppString += "}\n"

    cppFP = open(cppName, "w")
    cppFP.write(cppString)
    cppFP.close()


def manager_common(headerName, dataName, dataBase, memLocs, bssName, bssBase, bssSizePerThread, cppName, threadList, signatureSize, regBitWidth, numExecutions, platform, strideType, verbosity):

    if (platform == "linuxpthread"):
        # Data section and BSS section
        generate_data_section(dataName, memLocs, strideType)
        if (verbosity > 0):
            print("Data binary file %s generated (base 0x%X, size %d)" % (dataName, dataBase, memLocs * 4))
        bssSize = bssSizePerThread * len(threadList)
        generate_bss_section(bssName, bssSize)
        if (verbosity > 0):
            print("BSS binary file %s generated (base 0x%X, size %d)" % (bssName, bssBase, bssSize))
        generate_test_manager(cppName, headerName, threadList, bssBase, bssSizePerThread, signatureSize, regBitWidth, numExecutions, strideType)
        if (verbosity > 0):
            print("Test manager %s generated" % (cppName))

####################################################################
# Compute signature size (maximum signature size across all threads)
####################################################################
def compute_max_signature_size(intermediate, regBitWidth):
    maxSignatureFlushCount = 0
    perthreadSignatureSizes = dict()
    for thread in intermediate:
        pathCount = 0
        signatureFlushCount = 0
        for intermediateCode in intermediate[thread]:
            if (intermediateCode["type"] == "profile"):
                # reg, targets
                if ((pathCount * len(intermediateCode["targets"])) > ((1 << regBitWidth) - 1)):
                    pathCount = 0
                    signatureFlushCount += 1
                if (pathCount == 0):
                    pathCount = len(intermediateCode["targets"])
                else:
                    pathCount = pathCount * len(intermediateCode["targets"])
        perthreadSignatureSizes[thread] = (signatureFlushCount + 1) * regBitWidth / 8
        if (signatureFlushCount > maxSignatureFlushCount):
            maxSignatureFlushCount = signatureFlushCount
    # Number of bytes for each signature
    temp = (maxSignatureFlushCount + 1) * regBitWidth / 8
    # Log2 ceiling function
    power2Boundary = 1
    while (power2Boundary < temp):
        power2Boundary <<= 1
    return [max(power2Boundary, regBitWidth / 8), perthreadSignatureSizes]
