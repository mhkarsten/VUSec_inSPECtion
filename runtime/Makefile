# overwritten in setup.py
OBJDIR         ?= obj
LLVM_VERSION   ?= 16.0.1

PKG_CONFIG     := python ../setup.py pkg-config
BUILTIN_CFLAGS := `$(PKG_CONFIG) llvm-passes-builtin-$(LLVM_VERSION) --runtime-cflags`

CXX      := g++
CXXFLAGS := -O2 -fpic -Wall -Wextra -march=native
LIB      := libstacktrack.so
OBJS     := register_alloc.o

.PHONY: all clean

all: $(OBJDIR)/$(LIB)

$(OBJDIR)/$(LIB): $(addprefix $(OBJDIR)/,$(OBJS))
	$(CXX) -shared -static-libstdc++ -o $@ $^

$(OBJDIR)/%.o: %.cpp | $(OBJDIR)
	$(CXX) -c $(CXXFLAGS) -o $@ $<

$(OBJDIR):
	mkdir -p $@

clean:
	rm -rf $(OBJDIR)