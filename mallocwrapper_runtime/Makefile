# overwritten in setup.py
OBJDIR         ?= obj
LLVM_VERSION   ?= 16.0.1

PKG_CONFIG     := python ../setup.py pkg-config

CC       := ../build/packages/llvm-16.0.1/install/bin/clang
CFLAGS 	 := -O2 -fpic -Wall -Wextra -march=native -fno-builtin
LIB      := libmallocwrap.so
OBJS     := mallocwrapper.o

.PHONY: all clean

all: $(OBJDIR)/$(LIB)

$(OBJDIR)/$(LIB): $(addprefix $(OBJDIR)/,$(OBJS))
	$(CC) -shared -o $@ $^

$(OBJDIR)/%.o: %.c | $(OBJDIR)
	$(CC) -c $(CFLAGS) -o $@ $< 

$(OBJDIR):
	mkdir -p $@

clean:
	rm -rf $(OBJDIR)