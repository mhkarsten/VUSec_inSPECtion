.PHONY: clean defence_examples run_alloc_test dirs clean_stacktrack

CC=build/packages/llvm-16.0.1/install/bin/clang
override CFLAGS+=-O0 -g -fno-omit-frame-pointer -Wall

SRCDIR=examples
UTILSRC=utils
ODIR=bin
LIBDIR=lib
DIFFDIR=diff_out
IRDIR=ir_out

clean_stacktrack:
	rm -rf build/packages/libstacktrack-runtime
	rm -rf build/packages/libmallocwrapper-runtime
	rm -rf build/targets/hello-world
	rm -rf build/packages/llvm-passes-stacktrack

clean:
	-rm -f $(ODIR)/*.o
	-rm -f $(IRDIR)/*.out
	-rm -f $(DIFFDIR)/*.txt
	-rm -f $(LIBDIR)/*.so

dirs:
	mkdir -p $(SRCDIR)
	mkdir -p $(UTILSRC)
	mkdir -p $(ODIR)
	mkdir -p $(LIBDIR)
	mkdir -p $(DIFFDIR)
	mkdir -p $(IRDIR)

mallocwrapper: $(UTILSRC)/mallocwrapper.c | dirs
	$(CC) $(CFLAGS) -c -fno-builtin -fPIC -o $(ODIR)/$@.o $^ 
	$(CC) $(CFLAGS) -o $(LIBDIR)/$@.so -shared $(ODIR)/$@.o 

alloc_test: $(SRCDIR)/test.c | dirs
	$(CC) $(CFLAGS) -o $(ODIR)/$@.o $^ 

run_alloc_test: mallocwrapper alloc_test
	LD_PRELOAD="$(LIBDIR)/mallocwrapper.so" ./$(ODIR)/alloc_test.o

defence_examples: | dirs
	python utils/ir_generator.py


# For each defence, look at which instructions it instruments
# Then for each instruction provide examples in IR and such

