# MTraceCheck

This project provides a memory consistency validation framework, called MTraceCheck. Our ISCA (International Symposium of Computer Architecture) 2017 paper (http://doi.acm.org/10.1145/3079856.3080235) describes technical details.

## Contents
1. Constrained-random test generator
2. Simple architectural simulator for multi-core memory subsystem
3. Code instrumentator for memory-access interleaving signature
4. Collective graph checker

## Code structure
### src_main
Most source code files, except for collective graph checker, are included in this directory. Refer to this [README](src_main/README.md) for detail.

### src_tsort
Source code for collective graph checker. Refer to this [README](src_tsort/README.md) for detail.

### gem5_bug_injection

### gui


