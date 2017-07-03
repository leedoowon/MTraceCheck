
CFLAGS=-I.
#CFLAGS=-I. -DDIFF
CFLAGS_DEBUG=$(CFLAGS) -g -DDEBUG
CFLAGS_TIME=$(CFLAGS) -DTIME_MEASURE
CFLAGS_FREE=$(CFLAGS) -DFREE_SUCCESSOR

SRCDIR=../src
PROG_FILE=../exp/160812_codegen_x86/prog_t4_o100_l64.txt
PROFILE_FILE=../exp/160812_codegen_x86/profile_t4_o100_l64.txt
SIGNATURE_FILE=../exp/160812_codegen_x86/signature_t4_o100_l64.txt
NUM_UNIQUE_EXECS=65535
LAST_EXEC=$$(($(NUM_UNIQUE_EXECS)-1))

TARGET=tsort
SOURCES=fadvise.c xalloc-die.c xmalloc.c readtokens.c tsort.c
CROSS_COMPILE=

.PHONY: all

all: $(SOURCES)
	$(CROSS_COMPILE)gcc -O2 $(CFLAGS) -o $(TARGET) $(SOURCES)

time: $(SOURCES)
	$(CROSS_COMPILE)gcc -O2 $(CFLAGS_TIME) -o $(TARGET) $(SOURCES)

debug: $(SOURCES)
	$(CROSS_COMPILE)gcc -O0 $(CFLAGS_DEBUG) -o $(TARGET) $(SOURCES)

free: $(SOURCES)
	$(CROSS_COMPILE)gcc -O2 $(CFLAGS_FREE) -o $(TARGET) $(SOURCES)

run: tsort
	#./$(TARGET) input_sample.txt
	./$(TARGET) input_all.txt

create_tsort_input:
	python $(SRCDIR)/signature_decoder.py -v -d --profile-file=$(PROFILE_FILE) --output=hist_decoded.txt $(SIGNATURE_FILE)
	mkdir log
	python $(SRCDIR)/create_dot_graph.py -v --out-dir=log --gen-tsort --ignore-reg --program-file=$(PROGRAM_FILE) hist_decoded.txt

create_list:
	rm -f input_all.txt
	touch input_all.txt
	for i in `seq 0 $(LAST_EXEC)`; do echo "log/tsort$$i.txt" >> input_all.txt; done

clean:
	rm -f $(TARGET)
