#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Error: Check argument"
    exit 1
fi

if [[ $1 -eq 0 ]]; then
    echo "Original MESI_Two_Level protocol"
    cp src/mem/protocol/MESI_Two_Level-L1cache.sm_org src/mem/protocol/MESI_Two_Level-L1cache.sm
    cp src/mem/protocol/MESI_Two_Level-L2cache.sm_org src/mem/protocol/MESI_Two_Level-L2cache.sm
elif [[ $1 -eq 1 ]]; then
    echo "Bug 1 MESI_Two_Level protocol"
    cp src/mem/protocol/MESI_Two_Level-L1cache.sm_bug1 src/mem/protocol/MESI_Two_Level-L1cache.sm
    cp src/mem/protocol/MESI_Two_Level-L2cache.sm_org src/mem/protocol/MESI_Two_Level-L2cache.sm
elif [[ $1 -eq 3 ]]; then
    echo "Bug 3 MESI_Two_Level protocol"
    cp src/mem/protocol/MESI_Two_Level-L1cache.sm_bug3 src/mem/protocol/MESI_Two_Level-L1cache.sm
    cp src/mem/protocol/MESI_Two_Level-L2cache.sm_bug3 src/mem/protocol/MESI_Two_Level-L2cache.sm
else
    echo "Unrecognized bug number"
    # Note: Bug 2 should be set in gem5 command line, with original MESI_Two_Level protocol files
fi
