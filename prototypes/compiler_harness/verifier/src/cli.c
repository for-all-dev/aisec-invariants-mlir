#define _POSIX_C_SOURCE 200809L

#include "sps_harness/fixture_verifier.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct {
  uint8_t *data;
  size_t size;
} file_bytes;

static void usage(FILE *stream) {
  fputs("usage: sps-fixture-verify --trace TRACE --snapshot SNAPSHOT "
        "[--allow-synthetic-test-data | --restricted-output FILE]\n",
        stream);
}

static int read_file(const char *path, file_bytes *out) {
  FILE *file;
  long length;
  size_t read_size;
  memset(out, 0, sizeof(*out));
  file = fopen(path, "rb");
  if (!file) {
    fprintf(stderr, "error: cannot open %s: %s\n", path, strerror(errno));
    return 0;
  }
  if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
      fseek(file, 0, SEEK_SET) != 0) {
    fprintf(stderr, "error: cannot size %s\n", path);
    fclose(file);
    return 0;
  }
  if ((unsigned long)length > 4ul * 1024ul * 1024ul) {
    fprintf(stderr, "error: %s exceeds 4 MiB\n", path);
    fclose(file);
    return 0;
  }
  out->size = (size_t)length;
  out->data = (uint8_t *)malloc(out->size ? out->size : 1);
  if (!out->data) {
    fclose(file);
    return 0;
  }
  read_size = fread(out->data, 1, out->size, file);
  if (read_size != out->size || fclose(file) != 0) {
    fprintf(stderr, "error: cannot read %s\n", path);
    free(out->data);
    memset(out, 0, sizeof(*out));
    return 0;
  }
  return 1;
}

int main(int argc, char **argv) {
  const char *trace_path = NULL;
  const char *snapshot_path = NULL;
  const char *restricted_output = NULL;
  int allow_synthetic_test_data = 0;
  file_bytes trace = {0}, snapshot = {0};
  sps_fixture_actual *actual = NULL;
  sps_fixture_result *result = NULL;
  sps_fixture_result_view view;
  sps_fixture_status status;
  char *json = NULL;
  size_t json_size = 0;
  int i, exit_code = 2;
  for (i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--trace") == 0 && i + 1 < argc)
      trace_path = argv[++i];
    else if (strcmp(argv[i], "--snapshot") == 0 && i + 1 < argc)
      snapshot_path = argv[++i];
    else if (strcmp(argv[i], "--restricted-output") == 0 && i + 1 < argc)
      restricted_output = argv[++i];
    else if (strcmp(argv[i], "--allow-synthetic-test-data") == 0)
      allow_synthetic_test_data = 1;
    else {
      usage(stderr);
      return 2;
    }
  }
  if (!trace_path || !snapshot_path) {
    usage(stderr);
    return 2;
  }
  if (!read_file(trace_path, &trace) || !read_file(snapshot_path, &snapshot))
    goto done;
  status = sps_fixture_derive_trace(trace.data, trace.size, &actual);
  if (status != SPS_FIXTURE_STATUS_OK) goto done;
  status = sps_fixture_compare_snapshot(actual, snapshot.data, snapshot.size,
                                        &result);
  if (status != SPS_FIXTURE_STATUS_OK) goto done;
  if (sps_fixture_result_get_view(result, &view) != SPS_FIXTURE_STATUS_OK)
    goto done;
  if (!restricted_output &&
      view.sensitivity == SPS_FIXTURE_SENSITIVITY_RESTRICTED) {
    fputs("error: Restricted result requires --restricted-output; refusing "
          "stdout serialization\n", stderr);
    goto done;
  }
  if (!restricted_output &&
      view.sensitivity == SPS_FIXTURE_SENSITIVITY_SYNTHETIC_TEST_DATA &&
      !allow_synthetic_test_data) {
    fputs("error: SyntheticTestData stdout requires the out-of-band "
          "--allow-synthetic-test-data assertion; refusing serialization\n",
          stderr);
    goto done;
  }
  status = sps_fixture_result_write_json(result, NULL, 0, &json_size);
  if (status != SPS_FIXTURE_STATUS_BUFFER_TOO_SMALL &&
      status != SPS_FIXTURE_STATUS_OK)
    goto done;
  json = (char *)malloc(json_size ? json_size : 1);
  if (!json) goto done;
  status = sps_fixture_result_write_json(result, json, json_size, &json_size);
  if (status != SPS_FIXTURE_STATUS_OK) goto done;
  if (restricted_output) {
    int flags = O_WRONLY | O_CREAT | O_EXCL;
    int fd;
    FILE *output;
    int output_ok = 1;
#ifdef O_NOFOLLOW
    flags |= O_NOFOLLOW;
#endif
    fd = open(restricted_output, flags, (mode_t)0600);
    if (fd < 0) {
      fprintf(stderr,
              "error: cannot exclusively create restricted output: %s\n",
              strerror(errno));
      goto done;
    }
    if (fchmod(fd, (mode_t)0600) != 0) {
      close(fd);
      unlink(restricted_output);
      goto done;
    }
    output = fdopen(fd, "wb");
    if (!output) {
      close(fd);
      unlink(restricted_output);
      goto done;
    }
    if (json_size && fwrite(json, 1, json_size, output) != json_size)
      output_ok = 0;
    if (fputc('\n', output) == EOF) output_ok = 0;
    if (fflush(output) != 0) output_ok = 0;
    if (fsync(fileno(output)) != 0) output_ok = 0;
    if (fclose(output) != 0) output_ok = 0;
    if (!output_ok) {
      unlink(restricted_output);
      goto done;
    }
  } else {
    if (json_size && fwrite(json, 1, json_size, stdout) != json_size) goto done;
    fputc('\n', stdout);
  }
  exit_code = view.comparison == SPS_FIXTURE_COMPARISON_MATCHED
                  ? 0
                  : view.comparison == SPS_FIXTURE_COMPARISON_MISMATCHED ? 1
                                                                        : 2;
done:
  free(json);
  sps_fixture_result_destroy(result);
  sps_fixture_actual_destroy(actual);
  free(trace.data);
  free(snapshot.data);
  return exit_code;
}
