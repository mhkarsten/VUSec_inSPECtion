# overwritten in setup.py
OBJDIR         ?= obj
LLVM_VERSION   ?= 16.0.1

PKG_CONFIG     := python ../../setup.py pkg-config

CXX      := ../../build/packages/llvm-16.0.1/install/bin/clang++
CXXFLAGS := -O2  -fpic -Wall -Wextra -march=native `llvm-config --cxxflags`
LIB      := libstacktrack.so
OBJS     := register_alloc.o

.PHONY: all clean

all: $(OBJDIR)/$(LIB)

$(OBJDIR)/$(LIB): $(addprefix $(OBJDIR)/,$(OBJS))
	$(CXX) -shared -static-libstdc++ -o $@ $^ `llvm-config --ldflags --libs`

$(OBJDIR)/%.o: %.cpp | $(OBJDIR)
	$(CXX) -c $(CXXFLAGS) -o $@ $< 

$(OBJDIR):
	mkdir -p $@

clean:
	rm -rf $(OBJDIR)