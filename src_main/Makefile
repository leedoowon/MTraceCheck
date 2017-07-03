# gen_mtrand.py arguments
# [# threads] [# instructions] [# memory locations] [# outstanding ops]

all: bug_injection_cycle

bug_injection_cycle:
	python cycle_checker.py -v --ignore-reg --program-file=../exp/161020_gem5_bug_injection/gen_x86_4_50_8_1024_rand35/prog.txt --wo-file=../exp/161020_gem5_bug_injection/gen_x86_4_50_8_1024_rand35/wo.txt ../exp/161020_gem5_bug_injection/gen_x86_4_50_8_1024_rand35/hist_decoded.txt

gem5_cycle_check:
	-mkdir log
	python signature_decoder.py --profile-file=../exp/160812_codegen_x86/profile.txt --output=hist_decoded.txt ../exp/160812_codegen_x86/signature1.txt
	python create_dot_graph.py -v --out-dir=log --gen-tsort --program-file=../exp/160812_codegen_x86/prog.txt --wo-file=../exp/160812_codegen_x86/wo.txt --ignore-reg --no-dot hist_decoded.txt
	../src_tsort/tsort_conv log/tsort_list.txt
	python cycle_checker.py -v --ignore-reg --program-file=../exp/160812_codegen_x86/prog.txt --wo-file=../exp/160812_codegen_x86/wo.txt hist_decoded.txt

preexp_161018:
	-mkdir log
	python signature_decoder.py --profile-file=../exp/160812_codegen_x86/profile.txt --output=hist_decoded.txt ../exp/160812_codegen_x86/signature1.txt
	python create_dot_graph.py -v --out-dir=log --gen-tsort --program-file=../exp/160812_codegen_x86/prog.txt --wo-file=../exp/160812_codegen_x86/wo.txt --ignore-reg --no-dot hist_decoded.txt
	python cycle_checker.py -v --ignore-reg --program-file=../exp/160812_codegen_x86/prog.txt --wo-file=../exp/160812_codegen_x86/wo.txt hist_decoded.txt

preexp_161017:
	python gen_mtrand.py -v --gen-program --threads=2 --insts=50 --locs=32 --exec=1 --consistency-model=tso
	#python gen_mtrand.py -v --gen-program --threads=2 --insts=50 --locs=32 --exec=1 --consistency-model=wo
	python value_profiler.py -v prog.txt
	python cycle_checker.py -v -d --program-file=prog.txt --wo-file=wo.txt hist.txt  # No --ignore-reg
	python create_dot_graph.py -v --out-dir=log --gen-tsort --program-file=prog.txt hist.txt  # No --ignore-reg

preexp_161002:
	python gen_mtrand.py -v --gen-program --threads=2 --insts=200 --locs=64 --exec=0
	python value_profiler.py -v prog.txt
	python codegen.py -vv --arch=x86 --reg-width=64 --dir=gen --prefix=test_t --suffix=.S --data-addr=0x08000000 --mem-locs=64 --bss-addr=0x10000000 --execs=-1 --cpp-file=gen/test_manager.cpp --platform=baremetal test.txt

signature_decoder:
	python signature_decoder.py -v -d --profile-file=../exp/160812_codegen_x86/profile.txt --output=hist_decoded.txt ../exp/160812_codegen_x86/signature1.txt
	python cycle_checker.py -v -d --ignore-reg --program-file=../exp/160812_codegen_x86/prog.txt hist_decoded.txt

cycle_checker_bug_injection:
	#make clean
	#python gen_mtrand.py -v --threads=2 --insts=10 --locs=4 --exec=10 --gen-png --gen-program
	python cycle_checker.py -v -d --program-file=prog_bug.txt hist_bug.txt

cycle_checker:
	make clean
	python gen_mtrand.py -v --threads=2 --insts=10 --locs=4 --exec=10 --gen-program
	python cycle_checker.py -v -d --program-file=prog.txt hist.txt

randomness_statistics:
	make randomness_statistics_internal log_dir=log file_prefix=hist

randomness_statistics_internal:
	python rand_stat.py -v $(log_dir)/$(file_prefix)*.txt

create_dot_graph:
	#python create_dot_graph.py -v --out-dir=log --gen-png --program-file=prog.txt log/hist*.txt
	python create_dot_graph.py -v --out-dir=log --gen-tsort --ignore-reg --program-file=../exp/160812_codegen_x86/prog_tso.txt hist_decoded.txt

create_dot_graph_internal:

# The compare_graph below is an example of diffing two image files
compare_graph:
	neato -n -Tpng graph0.dot -ograph0.png
	compare graph0.png graph177.png difference.png

diff_preexp_160808_1:
	python gen_mtrand.py -v --threads=2 --insts=50 --locs=32 --exec=1000
	python rand_stat.py -v log/hist*.txt
	mv hist.txt hist_diff_1000_prog1.txt
	#python diff_hist.py -v --compare=baseline --baseline=0-999 --gen-csv --kmedoids --nummedoids=1 --percenttrials=10 hist_diff_1000_prog1.txt
	#python diff_hist.py -v --compare=baseline --baseline=0-999 --gen-csv --kmedoids --nummedoids=2 --percenttrials=10 hist_diff_1000_prog1.txt

diff_preexp_160808_2:
	python gen_mtrand.py -v --threads=4 --insts=50 --locs=32 --exec=1000
	python rand_stat.py -v log/hist*.txt
	mv hist.txt hist_diff_1000_prog2.txt

diff_preexp_160805:
	python diff_hist.py -v --compare=baseline --baseline=0-9 --gen-csv --kmedoids --nummedoids=2 --percenttrials=10 hist.txt

diff_preexp_160722:
	make clean
	python gen_mtrand.py -v --threads=2 --insts=10 --locs=4 --exec=10 --gen-png
	python diff_hist.py -v hist.txt

preexp_160719:
	make clean
	python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=1000
	#python gen_mtrand.py -v --threads=4 --insts=100 --locs=32 --exec=1000
	#python gen_mtrand.py -v --threads=2 --insts=50 --locs=32 --exec=1000
	#python gen_mtrand.py -v --threads=2 --insts=100 --locs=64 --exec=1000
	#python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=1000 --consistency-model=tso --outstanding=10
	#python gen_mtrand.py -v --threads=8 --insts=100 --locs=32 --exec=1000
	#python gen_mtrand.py -v --threads=2 --insts=10 --locs=4 --exec=10 --outstanding=10
	#python gen_mtrand.py -v --threads=2 --insts=10 --locs=4 --exec=10 --outstanding=1
	#python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=10000 --consistency-model=sc
	#wc -l md5_hist_uniq.txt
	#python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=15000 --consistency-model=sc
	#wc -l md5_hist_uniq.txt
	#python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=20000 --consistency-model=sc
	#wc -l md5_hist_uniq.txt
	#python gen_mtrand.py -v --threads=8 --insts=125 --locs=8192 --exec=1000 --consistency-model=sc
	#python gen_mtrand.py -v --threads=4 --insts=125 --locs=8192 --exec=1000 --consistency-model=sc
	#python gen_mtrand.py -v --threads=2 --insts=125 --locs=8192 --exec=1000 --consistency-model=sc
	#python gen_mtrand.py -v --threads=4 --insts=3000 --locs=16 --exec=1000 --consistency-model=tso
	#python gen_mtrand.py -v --threads=2 --insts=3000 --locs=1024 --exec=30 --consistency-model=sc

preexp_160720:
	make clean
	python gen_mtrand.py -v --threads=2 --insts=50 --locs=32 --exec=1000
	wc -l md5_hist_uniq.txt
	python gen_mtrand.py -v --threads=4 --insts=50 --locs=32 --exec=1000
	wc -l md5_hist_uniq.txt
	python gen_mtrand.py -v --threads=2 --insts=100 --locs=32 --exec=1000
	wc -l md5_hist_uniq.txt
	python gen_mtrand.py -v --threads=2 --insts=50 --locs=64 --exec=1000
	wc -l md5_hist_uniq.txt
	python gen_mtrand.py -v --threads=2 --insts=50 --locs=32 --exec=1000 --consistency-model=tso
	wc -l md5_hist_uniq.txt
	python gen_mtrand.py -v --threads=2 --insts=50 --locs=32 --exec=1000 --consistency-model=tso --outstanding=10
	wc -l md5_hist_uniq.txt

preexp: preexp.1 preexp.2 preexp.3 preexp.4 preexp.5

preexp.1:
	python gen_mtrand.py --thread=2 --insts=10 --locs=4 --outstanding=10
	mv md5_graph.txt md5_graph_t2_i10_m4.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i10_m4.txt
	mv md5_dump.txt  md5_dump_t2_i10_m4.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i10_m4.txt
	mv md5_hist.txt md5_hist_t2_i10_m4.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i10_m4.txt

preexp.2:
	python gen_mtrand.py --thread=2 --insts=50 --locs=16 --outstanding=50
	mv md5_graph.txt md5_graph_t2_i50_m16.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i50_m16.txt
	mv md5_dump.txt  md5_dump_t2_i50_m16.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i50_m16.txt
	mv md5_hist.txt md5_hist_t2_i50_m16.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i50_m16.txt

preexp.3:
	python gen_mtrand.py --thread=2 --insts=50 --locs=32 --outstanding=50
	mv md5_graph.txt md5_graph_t2_i50_m32.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i50_m32.txt
	mv md5_dump.txt  md5_dump_t2_i50_m32.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i50_m32.txt
	mv md5_hist.txt md5_hist_t2_i50_m32.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i50_m32.txt

preexp.4:
	python gen_mtrand.py --thread=2 --insts=100 --locs=16 --outstanding=100
	mv md5_graph.txt md5_graph_t2_i100_m16.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i100_m16.txt
	mv md5_dump.txt  md5_dump_t2_i100_m16.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i100_m16.txt
	mv md5_hist.txt md5_hist_t2_i100_m16.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i100_m16.txt

preexp.5:
	python gen_mtrand.py --thread=2 --insts=100 --locs=32 --outstanding=100
	mv md5_graph.txt md5_graph_t2_i100_m32.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i100_m32.txt
	mv md5_dump.txt  md5_dump_t2_i100_m32.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i100_m32.txt
	mv md5_hist.txt md5_hist_t2_i100_m32.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i100_m32.txt

preexp.6:
	python gen_mtrand.py --thread=2 --insts=500 --locs=32 --outstanding=500
	mv md5_graph.txt md5_graph_t2_i100_m32.txt
	mv md5_graph_uniq.txt md5_graph_uniq_t2_i100_m32.txt
	mv md5_dump.txt  md5_dump_t2_i100_m32.txt
	mv md5_dump_uniq.txt  md5_dump_uniq_t2_i100_m32.txt
	mv md5_hist.txt md5_hist_t2_i100_m32.txt
	mv md5_hist_uniq.txt md5_hist_uniq_t2_i100_m32.txt

clean:
	rm -f *.pyc
	rm -f dump.txt prog.txt hist.txt hist_decoded.txt test.txt
	rm -f md5_*.txt
	rm -f log/graph[0-9]*.dot log/dump[0-9]*.txt log/hist[0-9]*.txt
	rm -r log
	rm -rf gen
