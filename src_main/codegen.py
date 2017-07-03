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
import parse_intermediate
import codegen_common
import codegen_x86
import codegen_arm

parser = argparse.ArgumentParser(description="Arguments for %s" % __file__)
parser.add_argument("--verbose", "-v", action="count", default=0)
parser.add_argument("--debug", "-d", action="store_true", default=False)
parser.add_argument("--arch", default=None)
parser.add_argument("--reg-width", type=int, default=None)
parser.add_argument("--dir", default="asm")
parser.add_argument("--prefix", default="gen_t")  # test_t0.s
parser.add_argument("--suffix", default=".s")
parser.add_argument("--data-addr", default="0x800000")  # NOTE: This is string type. Requires type conversion to integer
parser.add_argument("--mem-locs", type=int, default=None)
parser.add_argument("--data-file", default="data.bin")
parser.add_argument("--bss-addr", default="0xC00000")  # NOTE: This is string type. Requires type conversion to integer
parser.add_argument("--bss-size-per-thread", default="0x100000")
parser.add_argument("--bss-file", default="bss.bin")
parser.add_argument("--result_addr", default="0x400000C0")  # This argument is used only for baremetal system
parser.add_argument("--execs", type=int, default=-1)
parser.add_argument("--cpp-file", default="test_manager.cpp")
parser.add_argument("--header-file", default="config.h")
parser.add_argument("--platform", default="linuxpthread")  # linuxpthread or baremetal
parser.add_argument("--profile-file", default=None)
parser.add_argument("--no-print", action="store_true", default=False)
parser.add_argument("--cores", type=int, default=-1)
parser.add_argument("--stride-type", type=int, default=0)
parser.add_argument("--exp-static-info", default=None)
parser.add_argument("--exp-original-time", action="store_true", default=False)
parser.add_argument("input", metavar="intermediate program file", help="intermediate program description to be processed")
args = parser.parse_args()
assert(args.data_addr.startswith("0x"))
assert(args.bss_addr.startswith("0x"))
assert(args.bss_size_per_thread.startswith("0x"))
assert(args.result_addr.startswith("0x"))

verbosity = args.verbose


if __name__ == "__main__":
    os.system("mkdir -pv %s" % (args.dir))
    textNamePrefix = "%s/%s" % (args.dir, args.prefix)
    textNameSuffix = args.suffix
    headerPath = "%s/%s" % (args.dir, args.header_file)
    dataBase = int(args.data_addr, 16)
    bssBase = int(args.bss_addr, 16)
    bssSizePerThread = int(args.bss_size_per_thread, 16)
    resultBase = int(args.result_addr, 16)
    if (args.cores == -1):
        if (args.arch == "x86"):
            numCores = 4
        elif (args.arch == "arm"):
            numCores = 8
        else:
            print("Error: Unrecognized architecture %s" % args.arch)
            print("       Cannot decide number of cores")
            assert(False)
    else:
        numCores = args.cores

    returnDict = parse_intermediate.parseIntermediate(args.input, verbosity)
    header = returnDict["header"]
    intermediate = returnDict["intermediate"]

    # ISA-independent code
    threadList = intermediate.keys()
    [signatureSize, perthreadSignatureSizes] = codegen_common.compute_max_signature_size(intermediate, args.reg_width)
    if (args.execs == -1):
        numExecutions = bssSizePerThread / signatureSize
    else:
        assert(args.execs <= bssSizePerThread / signatureSize)
        numExecutions = args.execs

    if (verbosity > 0):
        print("INFO: %d executions %d-byte signature for each execution and thread" % (numExecutions, signatureSize))
    if (args.exp_static_info != None):
        expFP = open(args.exp_static_info, "w")
        expFP.write("%d" % (signatureSize * len(perthreadSignatureSizes)))
        total = 0
        for thread in perthreadSignatureSizes:
            total += perthreadSignatureSizes[thread]
        expFP.write(" %d" % total)
        first = True
        for thread in perthreadSignatureSizes:
            if (first):
                expFP.write(" %d" % perthreadSignatureSizes[thread])
                first = False
            else:
                expFP.write("/%d" % perthreadSignatureSizes[thread])
        expFP.write("\n")
        expFP.close()
        del total, first

    # Test manager code (including header where necessary)
    if (args.platform == "linuxpthread"):
        if (args.arch == "x86"):
            codegen_x86.header_x86(headerPath, threadList, dataBase, args.mem_locs, bssBase, bssSizePerThread, signatureSize, args.reg_width, numExecutions, args.platform, args.no_print)
        elif (args.arch == "arm"):
            codegen_arm.header_arm(headerPath, threadList, dataBase, args.mem_locs, bssBase, resultBase, bssSizePerThread, signatureSize, args.reg_width, numExecutions, args.platform, args.no_print)
        codegen_common.manager_common(args.header_file, args.data_file, dataBase, args.mem_locs, args.bss_file, bssBase, bssSizePerThread, args.cpp_file, threadList, signatureSize, args.reg_width, numExecutions, args.platform, args.stride_type, verbosity)
    else:
        assert(args.platform == "baremetal")
        if (args.arch == "x86"):
            codegen_x86.header_x86(headerPath, threadList, dataBase, args.mem_locs, bssBase, bssSizePerThread, signatureSize, args.reg_width, numExecutions, args.platform, args.no_print)
            codegen_x86.common_x86("%s/%s" % (args.dir, "common.h"))
            codegen_x86.hash_x86("%s/%s" % (args.dir, "binary.cpp"))
            codegen_x86.manager_x86(args.cpp_file, args.header_file, threadList, signatureSize, args.reg_width, numCores, args.stride_type)
        elif (args.arch == "arm"):
            codegen_arm.header_arm(headerPath, threadList, dataBase, args.mem_locs, bssBase, resultBase, bssSizePerThread, signatureSize, args.reg_width, numExecutions, args.platform, args.no_print, args.exp_original_time)
            codegen_arm.manager_arm(args.cpp_file, args.header_file, threadList, signatureSize, args.reg_width, numCores, args.stride_type)
        else:
            print("Error: Unsupported ISA %s" % (args.arch))
            sys.exit(1)

    # Test threads code
    if (args.arch == "x86"):
        codegen_x86.test_x86(intermediate, textNamePrefix, textNameSuffix, args.header_file, dataBase, bssBase, bssSizePerThread, signatureSize, args.reg_width, numExecutions, True, args.platform, args.profile_file, numCores, args.stride_type, verbosity)
    elif (args.arch == "arm"):
        stackPointer = {0:0x40800000, 1:0x40900000, 2:0x40A00000, 3:0x40B00000, 4:0x40C00000, 5:0x40D00000, 6:0x40E00000, 7:0x40F00000}
        codegen_arm.test_arm(intermediate, textNamePrefix, textNameSuffix, args.header_file, dataBase, bssBase, bssSizePerThread, stackPointer, signatureSize, args.reg_width, numExecutions, True, args.platform, args.profile_file, numCores, args.stride_type, verbosity)
    else:
        print("Error: Unsupported ISA %s" % (args.arch))
        sys.exit(1)

