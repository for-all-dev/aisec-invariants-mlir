# Build the PMU constant-time probe.
#
# Dependencies (Debian/Ubuntu names):
#   clang llvm libbpf-dev bpftool linux-headers-$(uname -r)
# On the measurement host, and run pinned on the isolated rig (see
# measurement-rig.sh). perf_event_open needs perf_event_paranoid <= 0.

CLANG   ?= clang
BPFTOOL ?= bpftool
CC      ?= cc
ARCH    := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')

CFLAGS  ?= -O2 -g -Wall
BPF_CFLAGS := -O2 -g -target bpf -D__TARGET_ARCH_$(ARCH)

.PHONY: all clean
all: ctprobe

# 1. compile the BPF program
ctprobe.bpf.o: ctprobe.bpf.c
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

# 2. generate the skeleton header the loader includes
ctprobe.skel.h: ctprobe.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

# 3. build the userspace loader
ctprobe: ctprobe.c ctprobe.skel.h
	$(CC) $(CFLAGS) $< -o $@ -lbpf -lelf -lz -lm