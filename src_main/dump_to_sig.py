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

## For input, see dump file example at the end of this script
## For output, see signature_decoder.py. Occurrence count is set to 1
## Output example: 0x00c91437 0x0b8e9e0f: 1

metaAddr = 0x400000C0
startAddr = 0xA0000000
endAddr = None
signatureSize = None  # Size in word (4 bytes)
numSignatures = None

wordIdx = 0
signatureString = ""

lastAddr = None

inputFP = open(sys.argv[1], "r")
outputFP = open(sys.argv[2], "w")
for line in inputFP:
    #print line
    if (len(line) >= 9 and line[8] == ":"):
        # NOTE: This is not an absolutely correct way to parse only data.
        #       But probably this provides much better speed...
        tokens = line.split()
        currAddr = int(tokens[0][:-1],16)
        if lastAddr != None and currAddr <= lastAddr:
            print("Error: This script assumes an increasing address")
            print("       Meta data (0x40000000 range) should be dumped")
            print("       before signature data (0xA0000000 range)")
            sys.exit(1)
        if (endAddr != None):
            if (currAddr < endAddr and currAddr >= startAddr):
                for i in range(1, 5):
                    signatureString += " 0x%s" % tokens[i]
                    wordIdx += 1
                    if (wordIdx == signatureSize):
                        signatureString += ": 1\n"
                        outputFP.write(signatureString)
                        signatureString = ""
                        wordIdx = 0
            elif (currAddr >= endAddr):
                print("Terminated at line %s" % (line.rstrip()))
                break
        elif (currAddr == metaAddr):
            #400000c0: 00000020 a000c340 0000061a 00010000
            assert(signatureSize == None and endAddr == None and numSignatures == None)
            signatureSize = int(tokens[1], 16)  # size in word
            endAddr = int(tokens[2], 16)
            numSignatures = int(tokens[3], 16)
            print("start %x end %x signature size %d words, %d signatures" % (startAddr, endAddr, signatureSize, numSignatures))
            assert(endAddr == startAddr + (signatureSize * 4 * numSignatures))
        lastAddr = currAddr
    else:
        if (line.startswith("Exynos")):
            continue
        elif (line[0] == "#"):
            continue
        else:
            print("Warning: line %s is ignored" % line.rstrip())
            continue
inputFP.close()
outputFP.close()


"""
## Starting application at 0x41000860 ...
## Application terminated, rc = 0x0
40000000: 02030000 00040000 02025c00 00000100    .........\......
40000010: 000002cf 00000200 02030000 10408b10    ..............@.
40000020: 1001008c 20028880 08100000 00000000    ....... ........
40000030: 00090000 04010000 00000c00 020080a0    ................
40000040: 00240000 00040000 00000000 01100000    ..$.............
40000050: 00000000 00000040 38850100 40021201    ....@......8...@
40000060: 00000800 00402480 02000000 08000000    .....$@.........
40000070: 00000000 00000040 00008000 80500241    ....@.......A.P.
40000080: ffffffff ffffffff ffffffff ffffffff    ................
40000090: ffffff7f fffff7ff ffffffff ffffffff    ................
400000a0: ffffffff ffffffff ffffffff ffffffff    ................
400000b0: ff7fffff ffffffff ffffffff ffffffff    ................
400000c0: 0006b031 08000014 00edf95d 00edf95d    1.......]...]...
400000d0: 001b510c 08000014 019a20c1 019a20c1    .Q....... ... ..
400000e0: 001b510c 08000014 01f62dda 01f62dda    .Q.......-...-..
400000f0: 00000020 a000c340 0000061a 00010000    ................
40000100: 00110082 2101c812 00000000 00000800    .......!........
40000110: 00000000 00000000 01800000 c18002ba    ................
40000120: 00000000 00800425 00000000 00000000    ....%...........
40000130: 00400000 00000000 20352000 10a40204    ..@...... 5 ....
40000140: 00004010 00009083 00000000 08000000    .@..............
40000150: 00000000 00000000 00800110 04000008    ................
40000160: 00002010 02022008 00000000 00010000    . ... ..........
40000170: 00000000 00000401 0a020040 00085001    ........@....P..
40000180: ffffffff ffffffff ffffffef ffffffff    ................
40000190: ffffffff ffffffff ffffffff ffffffff    ................
400001a0: ffffffff ffffffff ffffffff ffffffff    ................
400001b0: ffffffff ffffffff ffffffff ffffffff    ................
400001c0: ffffffff ffffffff ffeffffe ffffffff    ................
400001d0: ffffffff ffffffff ffffffff ffffffff    ................
400001e0: ffffffff ffffffff ffffffff ffffffff    ................
400001f0: ffffffff ffff7fff ffffffff ffffffff    ................
Exynos5422 # md 0xa0000000
a0000000: c276e04a 0b24b9ff 0b24babc 00000000    J.v...$...$.....
a0000010: 87778fb2 4b4788c8 8d3990b7 8d3a5596    ..w...GK..9..U:.
a0000020: c276e04a 0b24b9ff 0b24babc 00000000    J.v...$...$.....
a0000030: 8fd74fb2 53a748c8 959950b7 959a1596    .O...H.S.P......
...
a000c300: c63e62cd 0f3acb6c 0f3acc29 00000000    .b>.l.:.).:.....
a000c310: 6cdcc000 b50c0908 f68ecbfd f68f8ca4    ...l............
a000c320: c63e62cd 0f3acb6c 0f3acc29 00000000    .b>.l.:.).:.....
a000c330: 6cdcc000 b50c0908 f68ecbfd f68f8d1c    ...l............
a000c340: 00042004 0010000c 00010000 00000000    . ..............
a000c350: 00000000 00000000 00000040 00110011    ........@.......
"""
