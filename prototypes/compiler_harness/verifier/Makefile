SHELL := /bin/sh

CC ?= cc
CXX ?= c++
AR ?= ar
PKG_CONFIG ?= pkg-config
BUILD ?= build
SANITIZE_BUILD ?= $(BUILD)/sanitize

CPPFLAGS += -I../include $(shell $(PKG_CONFIG) --cflags yaml-0.1)
CFLAGS ?= -O2
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Werror
CXXFLAGS ?= -O2
CXXFLAGS += -std=c++17 -Wall -Wextra -Wpedantic -Werror
LDLIBS += $(shell $(PKG_CONFIG) --libs yaml-0.1)

LIB_SOURCES := src/yaml.c src/model.c src/derive.c src/compare.c \
	src/json.c src/fixture_verifier.c
LIB_OBJECTS := $(LIB_SOURCES:src/%.c=$(BUILD)/%.o)
LIBRARY := $(BUILD)/libsps_fixture_verifier.a
CLI := $(BUILD)/sps-fixture-verify
UNIT := $(BUILD)/fixture_verifier_test
CXX_SMOKE := $(BUILD)/fixture_verifier_cpp_test

.PHONY: all check check-sanitize clean require-libyaml

all: require-libyaml $(CLI)

check: require-libyaml $(UNIT) $(CXX_SMOKE) $(CLI)
	$(UNIT)
	$(CXX_SMOKE)

check-sanitize:
	$(MAKE) check BUILD="$(SANITIZE_BUILD)" \
	  CFLAGS="-O1 -g -std=c11 -Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined -fno-omit-frame-pointer" \
	  CXXFLAGS="-O1 -g -std=c++17 -Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined -fno-omit-frame-pointer" \
	  LDLIBS="$(shell $(PKG_CONFIG) --libs yaml-0.1) -fsanitize=address,undefined"

require-libyaml:
	@$(PKG_CONFIG) --exists yaml-0.1 || { \
	  echo "error: libyaml development files are required (pkg-config yaml-0.1)" >&2; \
	  exit 1; \
	}

$(BUILD):
	mkdir -p $@

$(BUILD)/%.o: src/%.c src/internal.h ../include/sps_harness/fixture_verifier.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(LIBRARY): $(LIB_OBJECTS)
	$(AR) rcs $@ $^

$(BUILD)/cli.o: src/cli.c ../include/sps_harness/fixture_verifier.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(CLI): $(BUILD)/cli.o $(LIBRARY)
	$(CC) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/fixture_verifier_test.o: tests/fixture_verifier_test.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(UNIT): $(BUILD)/fixture_verifier_test.o $(LIBRARY)
	$(CC) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/fixture_verifier_cpp_test.o: tests/fixture_verifier_cpp_test.cpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

$(CXX_SMOKE): $(BUILD)/fixture_verifier_cpp_test.o $(LIBRARY)
	$(CXX) $(CXXFLAGS) $^ $(LDLIBS) -o $@

clean:
	rm -rf $(BUILD)
