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

TARGET_ARCH ?= riscv
TARGET_OS ?= baremetal
SIGNATURE ?= 0
NUM_THREADS ?= 8
NUM_INSTS ?= 200
NUM_LOCS ?= 32
NUM_EXECS ?= 1024
#NUM_EXECS ?= 1
STRIDE_TYPE ?= 2
FENCES_INCLUDED ?= 1
ENTRY_POINT_ADDRESS ?=
#ENTRY_POINT_ADDRESS ?= 0x40000000

RAND_SEED ?= 

GEN_DIR ?= gen
MANAGER_CPP = $(GEN_DIR)/test_manager.cpp
MANAGER_S = $(GEN_DIR)/test_manager.S
MANAGER_ELF = $(GEN_DIR)/test_manager.elf
DATA_FILE = $(GEN_DIR)/data.bin
BSS_FILE = $(GEN_DIR)/bss.bin
TMP_DATA_FILE=/tmp/mtdiag_data.tmp
TMP_BSS_FILE=/tmp/mtdiag_bss.tmp
EXECUTABLE = $(GEN_DIR)/test
DUMP_FILE = $(EXECUTABLE).dump
READELF_FILE = $(EXECUTABLE).readelf
M5THREADS_DIR = $(HOME)/research/progmm/m5threads-dcec9ee72f99

THREADS = $(shell seq 0 $$(($(NUM_THREADS)-1)))

# NOTE: The BSS size should be larger than (signature size) X (number of executions)
#       Please change the BSS_SIZE_PER_THREAD if codegen.py gives an error message about BSS section size
ifeq ($(shell test $(NUM_EXECS) -gt 262144; echo $$?),0)  # 262144 = 0x40000
BSS_SIZE_PER_THREAD = 0x4000000
else
BSS_SIZE_PER_THREAD = 0x1000000
endif

PROFILE_FLAGS =
ifneq ($(SIGNATURE),1)
PROFILE_FLAGS += --no-profile
endif

TEST_GEN_FLAGS =
ifdef RAND_SEED
TEST_GEN_FLAGS += --rand-seed=$(RAND_SEED)
endif
ifeq ($(FENCES_INCLUDED),1)
TEST_GEN_FLAGS += --with-fences
endif

########################################################################
# Architecture dependent settings
########################################################################
ifeq ($(TARGET_ARCH),x86)
PREFIX = 
CFLAGS =
ifdef ENTRY_POINT_ADDRESS
LDFLAGS = -Wl,--section-start=.text.init=$(ENTRY_POINT_ADDRESS)
else
LDFLAGS =
endif
ifeq ($(TARGET_OS),baremetal)
$(error This makefile does not support the x86 baremetal option yet.)
DATA_ADDR = 0x8000000
BSS_ADDR = 0x10000000
all: x86_baremetal
else ifeq ($(TARGET_OS),linuxpthread)
DATA_ADDR = 0x800000
BSS_ADDR = 0xC00000
all: x86_linuxpthread
endif

else ifeq ($(TARGET_ARCH),arm)

PREFIX = /z/odroid/gcc-linaro-arm-linux-gnueabihf-4.7-2013.04-20130415_linux/bin/arm-linux-gnueabihf-
CFLAGS = -static -march=armv7-a -marm -O3
ifdef ENTRY_POINT_ADDRESS
LDFLAGS = -Wl,--section-start=.text.init=$(ENTRY_POINT_ADDRESS)
else
LDFLAGS =
endif
DATA_ADDR = 0x50000000
BSS_ADDR = 0x60000000
ifeq ($(TARGET_OS),baremetal)
all: arm_baremetal
else ifeq ($(TARGET_OS),linuxpthread)
$(error This makefile does not support the ARM linuxpthread option yet.)
all: arm_linuxpthread
endif

else ifeq ($(TARGET_ARCH),riscv)

ifdef RISCV
RISCV_BIN = $(RISCV)/bin/
else
RISCV_BIN = /home/doowon/research/freedom/rocket-chip/riscv/bin/
endif
ifeq ($(TARGET_OS),baremetal)
PREFIX = $(RISCV_BIN)/riscv64-unknown-elf-
else
PREFIX = $(RISCV_BIN)/riscv64-unknown-linux-gnu-
endif
CFLAGS = -I./riscv
ifdef ENTRY_POINT_ADDRESS
LDFLAGS = -Wl,--section-start=.text.init=$(ENTRY_POINT_ADDRESS)
else
LDFLAGS =
endif
DATA_ADDR = 0x84000000
BSS_ADDR = 0x88000000
#DATA_ADDR = 0x60000000
#BSS_ADDR = 0x68000000
ifeq ($(TARGET_OS),baremetal)
all: riscv_baremetal
else ifeq ($(TARGET_OS),linuxpthread)
all: riscv_linuxpthread
endif

endif
# End of architecture dependent settings


test_gen_wo_signature_code:
	python gen_mtrand.py -v --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=32 --exec=1 --consistency-model=ro
	python value_profiler.py --no-profile -v prog.txt

test_gen_w_signature_code:
	python gen_mtrand.py -v --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=32 --exec=1 --consistency-model=ro
	python value_profiler.py -v prog.txt

test.txt: test_gen_wo_signature_code

codegen_x86_baremetal: test.txt
	python codegen.py -vv --arch=x86 --reg-width=64 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --bss-addr=$(BSS_ADDR) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(GEN_DIR)/test_manager.S --platform=baremetal test.txt

codegen_x86_linuxpthread: test.txt
	python codegen.py -v --arch=x86 --reg-width=64 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --data-file=$(DATA_FILE) --bss-addr=$(BSS_ADDR) --bss-size-per-thread=$(BSS_SIZE_PER_THREAD) --bss-file=$(BSS_FILE) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(MANAGER_CPP) --profile-file=profile.txt test.txt

x86_linuxpthread:
	# Test generation (in intermediate form)
	python gen_mtrand.py -v $(TEST_GEN_FLAGS) --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=$(NUM_LOCS) --exec=0 --consistency-model=tso
	python value_profiler.py $(PROFILE_FLAGS) -v prog.txt
	# Code generation (for target architecture)
	python codegen.py -v --arch=x86 --reg-width=64 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --data-file=$(DATA_FILE) --bss-addr=$(BSS_ADDR) --bss-size-per-thread=$(BSS_SIZE_PER_THREAD) --bss-file=$(BSS_FILE) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(MANAGER_CPP) --platform=linuxpthread --profile-file=profile.txt test.txt
	# Compile code
	$(PREFIX)ld -b binary -r -o $(TMP_DATA_FILE) $(DATA_FILE)
	$(PREFIX)ld -b binary -r -o $(TMP_BSS_FILE) $(BSS_FILE)
	$(PREFIX)objcopy --rename-section .data=.testmem,noload,alloc $(TMP_DATA_FILE)
	$(PREFIX)objcopy --rename-section .data=.testbss,noload,alloc $(TMP_BSS_FILE)
	$(PREFIX)g++ $(CFLAGS) -c -o $(MANAGER_ELF) $(MANAGER_CPP)
	$(foreach thread_id,$(THREADS),$(PREFIX)gcc $(CFLAGS) -c -o $(GEN_DIR)/test_t$(thread_id).elf $(GEN_DIR)/test_t$(thread_id).S;)
	$(PREFIX)g++ -O3 -static -Wl,--section-start=.testmem=$(DATA_ADDR),--section-start=.testbss=$(BSS_ADDR) $(LDFLAGS) -o $(EXECUTABLE) $(GEN_DIR)/*.elf $(TMP_DATA_FILE) $(TMP_BSS_FILE) $(M5THREADS_DIR)/pthread_x86.o
	# Post-processing
	$(PREFIX)objdump -D $(EXECUTABLE) > $(DUMP_FILE)
	$(PREFIX)readelf -W -a $(EXECUTABLE) > $(READELF_FILE)

arm_baremetal:
	# Test generation (in intermediate form)
	python gen_mtrand.py $(TEST_GEN_FLAGS) --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=$(NUM_LOCS) --exec=0 --consistency-model=ro
	python value_profiler.py $(PROFILE_FLAGS) prog.txt
	# Code generation (for target architecture)
	python codegen.py -v --arch=arm --reg-width=32 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --data-file=$(DATA_FILE) --bss-addr=$(BSS_ADDR) --bss-size-per-thread=$(BSS_SIZE_PER_THREAD) --bss-file=$(BSS_FILE) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(MANAGER_CPP) --platform=baremetal --profile-file=profile.txt test.txt
	# Compile code
	$(PREFIX)g++ $(CFLAGS) -c -o $(MANAGER_ELF) $(MANAGER_CPP)
	$(foreach thread_id,$(THREADS),$(PREFIX)gcc $(CFLAGS) -c -o $(GEN_DIR)/test_t$(thread_id).elf $(GEN_DIR)/test_t$(thread_id).S;)
	$(PREFIX)g++ -O3 -static -T arm/link.ld $(LDFLAGS) -o $(EXECUTABLE) $(GEN_DIR)/*.elf
	## Post-processing
	$(PREFIX)objcopy -O binary $(EXECUTABLE) $(EXECUTABLE).bin
	$(PREFIX)objdump -D $(EXECUTABLE) > $(DUMP_FILE)
	$(PREFIX)readelf -W -a $(EXECUTABLE) > $(READELF_FILE)

riscv_baremetal:
	# Test generation (in intermediate form)
	python gen_mtrand.py $(TEST_GEN_FLAGS) --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=$(NUM_LOCS) --exec=0 --consistency-model=ro
	python value_profiler.py $(PROFILE_FLAGS) prog.txt
	# Code generation (for target architecture)
	python codegen.py -v --arch=riscv --cores=$(NUM_THREADS) --reg-width=64 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --data-file=$(DATA_FILE) --bss-addr=$(BSS_ADDR) --bss-size-per-thread=$(BSS_SIZE_PER_THREAD) --bss-file=$(BSS_FILE) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(MANAGER_S) --platform=baremetal --profile-file=profile.txt test.txt
	# Compile code
	$(PREFIX)g++ $(CFLAGS) -c -o $(MANAGER_ELF) $(MANAGER_S)
	$(foreach thread_id,$(THREADS),$(PREFIX)gcc $(CFLAGS) -c -o $(GEN_DIR)/test_t$(thread_id).elf $(GEN_DIR)/test_t$(thread_id).S;)
	$(PREFIX)g++ -O3 -static -nostdlib -nostartfiles -T riscv/link.ld $(LDFLAGS) -o $(EXECUTABLE) $(GEN_DIR)/*.elf
	## Post-processing
	$(PREFIX)objdump -D $(EXECUTABLE) > $(DUMP_FILE)
	$(PREFIX)readelf -W -a $(EXECUTABLE) > $(READELF_FILE)

riscv_linuxpthread:
	# Test generation (in intermediate form)
	python gen_mtrand.py $(TEST_GEN_FLAGS) --gen-program --threads=$(NUM_THREADS) --insts=$(NUM_INSTS) --locs=$(NUM_LOCS) --exec=0 --consistency-model=ro
	python value_profiler.py $(PROFILE_FLAGS) prog.txt
	# Code generation (for target architecture)
	python codegen.py -v --arch=riscv --cores=$(NUM_THREADS) --reg-width=64 --dir=$(GEN_DIR) --prefix=test_t --suffix=.S --data-addr=$(DATA_ADDR) --mem-locs=$(NUM_LOCS) --data-file=$(DATA_FILE) --bss-addr=$(BSS_ADDR) --bss-size-per-thread=$(BSS_SIZE_PER_THREAD) --bss-file=$(BSS_FILE) --execs=$(NUM_EXECS) --stride-type=$(STRIDE_TYPE) --manager-file=$(MANAGER_CPP) --platform=linuxpthread --profile-file=profile.txt test.txt
	# Compile code
	$(PREFIX)ld -b binary -o $(TMP_DATA_FILE) $(DATA_FILE)
	$(PREFIX)ld -b binary -o $(TMP_BSS_FILE) $(BSS_FILE)
	$(PREFIX)objcopy --strip-symbol=__global_pointer$$ --strip-symbol=__bss_start --strip-symbol=_edata --strip-symbol=_end $(TMP_DATA_FILE)
	$(PREFIX)objcopy --strip-symbol=__global_pointer$$ --strip-symbol=__bss_start --strip-symbol=_edata --strip-symbol=_end $(TMP_BSS_FILE)
	$(PREFIX)objcopy --rename-section .data=.testmem,noload,alloc $(TMP_DATA_FILE)
	$(PREFIX)objcopy --rename-section .data=.testbss,noload,alloc $(TMP_BSS_FILE)
	$(PREFIX)g++ $(CFLAGS) -c -o $(MANAGER_ELF) $(MANAGER_CPP)
	$(foreach thread_id,$(THREADS),$(PREFIX)gcc $(CFLAGS) -c -o $(GEN_DIR)/test_t$(thread_id).elf $(GEN_DIR)/test_t$(thread_id).S;)
	$(PREFIX)g++ -O3 -static -Wl,--section-start=.testmem=$(DATA_ADDR),--section-start=.testbss=$(BSS_ADDR) -pthread $(LDFLAGS) -o $(EXECUTABLE) $(GEN_DIR)/*.elf $(TMP_DATA_FILE) $(TMP_BSS_FILE)
	## Post-processing
	$(PREFIX)objdump -D $(EXECUTABLE) > $(DUMP_FILE)
	$(PREFIX)readelf -W -a $(EXECUTABLE) > $(READELF_FILE)

clean:
	rm -f *.pyc
	rm -f dump.txt prog.txt hist.txt hist_decoded.txt test.txt wo.txt profile.txt
	rm -rf log $(GEN_DIR)

.PHONY: all clean
