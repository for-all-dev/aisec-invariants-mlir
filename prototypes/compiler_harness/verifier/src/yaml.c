#include "internal.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <yaml.h>

#define SPSV_MAX_INPUT (4u * 1024u * 1024u)
#define SPSV_MAX_DEPTH 64u
#define SPSV_MAX_NODES 100000u

typedef struct {
  yaml_parser_t parser;
  size_t nodes;
  int out_of_memory;
  spsv_parse_error *error;
} spsv_yaml_reader;

typedef struct {
  char *data;
  size_t size;
  size_t capacity;
  int failed;
} spsv_buffer;

char *spsv_strdup(const char *value) {
  size_t n;
  char *copy;
  if (!value) return NULL;
  n = strlen(value);
  if (n == SIZE_MAX) return NULL;
  copy = (char *)malloc(n + 1);
  if (!copy) return NULL;
  memcpy(copy, value, n + 1);
  return copy;
}

static sps_fixture_source_location spsv_location(yaml_mark_t mark) {
  sps_fixture_source_location out;
  out.present = 1;
  out.byte_offset = mark.index;
  out.line = mark.line + 1;
  out.column = mark.column + 1;
  return out;
}

static int spsv_fail(spsv_yaml_reader *reader, yaml_mark_t mark,
                     const char *message) {
  if (!reader->error->message) {
    reader->error->message = spsv_strdup(message);
    if (!reader->error->message) reader->out_of_memory = 1;
    reader->error->location = spsv_location(mark);
  }
  return 0;
}

static int spsv_parser_fail(spsv_yaml_reader *reader) {
  if (reader->parser.error == YAML_MEMORY_ERROR) reader->out_of_memory = 1;
  return spsv_fail(reader, reader->parser.problem_mark,
                   reader->parser.problem ? reader->parser.problem
                                          : "invalid YAML");
}

static spsv_node *spsv_new_node(spsv_yaml_reader *reader,
                                spsv_node_kind kind, yaml_mark_t mark) {
  spsv_node *node;
  if (++reader->nodes > SPSV_MAX_NODES) {
    spsv_fail(reader, mark, "YAML node limit exceeded");
    return NULL;
  }
  node = (spsv_node *)calloc(1, sizeof(*node));
  if (!node) {
    reader->out_of_memory = 1;
    spsv_fail(reader, mark, "out of memory");
    return NULL;
  }
  node->kind = kind;
  node->location = spsv_location(mark);
  return node;
}

void spsv_node_destroy(spsv_node *node) {
  size_t i;
  if (!node) return;
  switch (node->kind) {
  case SPSV_NODE_STRING:
    free(node->as.string);
    break;
  case SPSV_NODE_SEQUENCE:
    for (i = 0; i < node->as.sequence.count; ++i)
      spsv_node_destroy(node->as.sequence.items[i]);
    free(node->as.sequence.items);
    break;
  case SPSV_NODE_MAPPING:
    for (i = 0; i < node->as.mapping.count; ++i) {
      free(node->as.mapping.items[i].key);
      spsv_node_destroy(node->as.mapping.items[i].value);
    }
    free(node->as.mapping.items);
    break;
  case SPSV_NODE_BOOL:
  case SPSV_NODE_INTEGER:
    break;
  }
  free(node);
}

static int spsv_sequence_push(spsv_node *sequence, spsv_node *item) {
  spsv_node **grown;
  size_t capacity;
  if (sequence->as.sequence.count == sequence->as.sequence.capacity) {
    capacity = sequence->as.sequence.capacity
                   ? sequence->as.sequence.capacity * 2
                   : 4;
    if (capacity > SIZE_MAX / sizeof(*grown)) return 0;
    grown = (spsv_node **)realloc(sequence->as.sequence.items,
                                 capacity * sizeof(*grown));
    if (!grown) return 0;
    sequence->as.sequence.items = grown;
    sequence->as.sequence.capacity = capacity;
  }
  sequence->as.sequence.items[sequence->as.sequence.count++] = item;
  return 1;
}

static int spsv_mapping_push(spsv_node *mapping, char *key,
                             spsv_node *value) {
  spsv_pair *grown;
  size_t capacity;
  if (mapping->as.mapping.count == mapping->as.mapping.capacity) {
    capacity = mapping->as.mapping.capacity
                   ? mapping->as.mapping.capacity * 2
                   : 4;
    if (capacity > SIZE_MAX / sizeof(*grown)) return 0;
    grown = (spsv_pair *)realloc(mapping->as.mapping.items,
                                capacity * sizeof(*grown));
    if (!grown) return 0;
    mapping->as.mapping.items = grown;
    mapping->as.mapping.capacity = capacity;
  }
  mapping->as.mapping.items[mapping->as.mapping.count].key = key;
  mapping->as.mapping.items[mapping->as.mapping.count].value = value;
  ++mapping->as.mapping.count;
  return 1;
}

static int spsv_scalar_is_null(const char *value) {
  return strcmp(value, "null") == 0 || strcmp(value, "Null") == 0 ||
         strcmp(value, "NULL") == 0 || strcmp(value, "~") == 0;
}

static size_t spsv_sign_offset(const char *value) {
  return value[0] == '-' || value[0] == '+' ? 1u : 0u;
}

static int spsv_canonical_integer_shape(const char *value) {
  size_t i = value[0] == '-' ? 1u : 0u;
  if (value[i] == '0') return i == 0 && value[i + 1] == '\0';
  if (value[i] < '1' || value[i] > '9') return 0;
  for (++i; value[i]; ++i)
    if (value[i] < '0' || value[i] > '9') return 0;
  return 1;
}

static int spsv_decimal_integer_shape(const char *value) {
  size_t i = spsv_sign_offset(value);
  if (value[i] < '0' || value[i] > '9') return 0;
  for (++i; value[i]; ++i)
    if (!((value[i] >= '0' && value[i] <= '9') || value[i] == '_'))
      return 0;
  return 1;
}

static int spsv_decimal_numeric_shape(const char *value) {
  size_t i = spsv_sign_offset(value);
  int digit = 0;
  if (!((value[i] >= '0' && value[i] <= '9') || value[i] == '.'))
    return 0;
  for (; value[i]; ++i) {
    char c = value[i];
    if (c >= '0' && c <= '9')
      digit = 1;
    else if (!(c == '.' || c == '_' || c == 'e' || c == 'E' || c == '+' ||
               c == '-'))
      return 0;
  }
  return digit;
}

static int spsv_base_numeric_shape(const char *value) {
  size_t i = spsv_sign_offset(value);
  return value[i] == '0' &&
         (value[i + 1] == 'x' || value[i + 1] == 'X' ||
          value[i + 1] == 'o' || value[i + 1] == 'O' ||
          value[i + 1] == 'b' || value[i + 1] == 'B');
}

static int spsv_sexagesimal_shape(const char *value) {
  size_t i = spsv_sign_offset(value);
  if (value[i] < '0' || value[i] > '9') return 0;
  while ((value[i] >= '0' && value[i] <= '9') || value[i] == '_') ++i;
  if (value[i++] != ':' || value[i] < '0' || value[i] > '9') return 0;
  while ((value[i] >= '0' && value[i] <= '9') || value[i] == '_') ++i;
  if (value[i] == '.') {
    ++i;
    while ((value[i] >= '0' && value[i] <= '9') || value[i] == '_') ++i;
  }
  return value[i] == '\0';
}

static int spsv_special_float_shape(const char *value) {
  size_t i = spsv_sign_offset(value);
  const char *body = value + i;
  return strcmp(body, ".inf") == 0 || strcmp(body, ".Inf") == 0 ||
         strcmp(body, ".INF") == 0 || strcmp(body, ".nan") == 0 ||
         strcmp(body, ".NaN") == 0 || strcmp(body, ".NAN") == 0;
}

static int spsv_scalar_integer(const char *value, int64_t *out) {
  char *end;
  long long parsed;
  if (!spsv_canonical_integer_shape(value)) return 0;
  errno = 0;
  parsed = strtoll(value, &end, 10);
  if (errno == ERANGE || *end != '\0') return 0;
  if (parsed < INT64_MIN || parsed > INT64_MAX) return 0;
  *out = (int64_t)parsed;
  return 1;
}

static int spsv_has_forbidden_numeric_shape(const char *value) {
  return spsv_decimal_integer_shape(value) ||
         spsv_decimal_numeric_shape(value) ||
         spsv_base_numeric_shape(value) || spsv_sexagesimal_shape(value) ||
         spsv_special_float_shape(value);
}

static spsv_node *spsv_parse_node(spsv_yaml_reader *reader,
                                  yaml_event_t *event, size_t depth);

static spsv_node *spsv_parse_sequence(spsv_yaml_reader *reader,
                                      yaml_event_t *start, size_t depth) {
  spsv_node *sequence;
  yaml_event_t event;
  sequence = spsv_new_node(reader, SPSV_NODE_SEQUENCE, start->start_mark);
  if (!sequence) return NULL;
  for (;;) {
    if (!yaml_parser_parse(&reader->parser, &event)) {
      spsv_parser_fail(reader);
      spsv_node_destroy(sequence);
      return NULL;
    }
    if (event.type == YAML_SEQUENCE_END_EVENT) {
      yaml_event_delete(&event);
      return sequence;
    }
    {
      spsv_node *item = spsv_parse_node(reader, &event, depth + 1);
      yaml_event_delete(&event);
      if (!item || !spsv_sequence_push(sequence, item)) {
        if (item) reader->out_of_memory = 1;
        spsv_node_destroy(item);
        spsv_fail(reader, start->start_mark, "out of memory");
        spsv_node_destroy(sequence);
        return NULL;
      }
    }
  }
}

static spsv_node *spsv_parse_mapping(spsv_yaml_reader *reader,
                                     yaml_event_t *start, size_t depth) {
  spsv_node *mapping;
  yaml_event_t key_event;
  mapping = spsv_new_node(reader, SPSV_NODE_MAPPING, start->start_mark);
  if (!mapping) return NULL;
  for (;;) {
    yaml_event_t value_event;
    char *key;
    size_t i;
    spsv_node *value;
    if (!yaml_parser_parse(&reader->parser, &key_event)) {
      spsv_parser_fail(reader);
      spsv_node_destroy(mapping);
      return NULL;
    }
    if (key_event.type == YAML_MAPPING_END_EVENT) {
      yaml_event_delete(&key_event);
      return mapping;
    }
    if (key_event.type != YAML_SCALAR_EVENT ||
        key_event.data.scalar.anchor || key_event.data.scalar.tag) {
      spsv_fail(reader, key_event.start_mark,
                "mapping keys must be untagged scalar strings");
      yaml_event_delete(&key_event);
      spsv_node_destroy(mapping);
      return NULL;
    }
    if (memchr(key_event.data.scalar.value, '\0',
               key_event.data.scalar.length) ||
        (key_event.data.scalar.length == 2 &&
         memcmp(key_event.data.scalar.value, "<<", 2) == 0)) {
      spsv_fail(reader, key_event.start_mark,
                "embedded NUL and merge keys are forbidden");
      yaml_event_delete(&key_event);
      spsv_node_destroy(mapping);
      return NULL;
    }
    key = spsv_strdup((const char *)key_event.data.scalar.value);
    if (!key) {
      reader->out_of_memory = 1;
      spsv_fail(reader, key_event.start_mark, "out of memory");
      yaml_event_delete(&key_event);
      spsv_node_destroy(mapping);
      return NULL;
    }
    for (i = 0; i < mapping->as.mapping.count; ++i) {
      if (strcmp(mapping->as.mapping.items[i].key, key) == 0) {
        free(key);
        spsv_fail(reader, key_event.start_mark, "duplicate mapping key");
        yaml_event_delete(&key_event);
        spsv_node_destroy(mapping);
        return NULL;
      }
    }
    yaml_event_delete(&key_event);
    if (!yaml_parser_parse(&reader->parser, &value_event)) {
      free(key);
      spsv_parser_fail(reader);
      spsv_node_destroy(mapping);
      return NULL;
    }
    value = spsv_parse_node(reader, &value_event, depth + 1);
    yaml_event_delete(&value_event);
    if (!value || !spsv_mapping_push(mapping, key, value)) {
      if (value) reader->out_of_memory = 1;
      free(key);
      spsv_node_destroy(value);
      spsv_fail(reader, start->start_mark, "out of memory");
      spsv_node_destroy(mapping);
      return NULL;
    }
  }
}

static spsv_node *spsv_parse_node(spsv_yaml_reader *reader,
                                  yaml_event_t *event, size_t depth) {
  spsv_node *node;
  const char *value;
  int64_t integer;
  if (depth > SPSV_MAX_DEPTH) {
    spsv_fail(reader, event->start_mark, "YAML nesting limit exceeded");
    return NULL;
  }
  if (event->type == YAML_ALIAS_EVENT) {
    spsv_fail(reader, event->start_mark, "YAML aliases are forbidden");
    return NULL;
  }
  if (event->type == YAML_SEQUENCE_START_EVENT) {
    if (event->data.sequence_start.anchor ||
        event->data.sequence_start.tag) {
      spsv_fail(reader, event->start_mark,
                "YAML anchors and explicit tags are forbidden");
      return NULL;
    }
    return spsv_parse_sequence(reader, event, depth);
  }
  if (event->type == YAML_MAPPING_START_EVENT) {
    if (event->data.mapping_start.anchor || event->data.mapping_start.tag) {
      spsv_fail(reader, event->start_mark,
                "YAML anchors and explicit tags are forbidden");
      return NULL;
    }
    return spsv_parse_mapping(reader, event, depth);
  }
  if (event->type != YAML_SCALAR_EVENT) {
    spsv_fail(reader, event->start_mark, "expected a YAML value");
    return NULL;
  }
  if (event->data.scalar.anchor || event->data.scalar.tag) {
    spsv_fail(reader, event->start_mark,
              "YAML anchors and explicit tags are forbidden");
    return NULL;
  }
  value = (const char *)event->data.scalar.value;
  if (memchr(event->data.scalar.value, '\0',
             event->data.scalar.length)) {
    spsv_fail(reader, event->start_mark,
              "embedded NUL scalars are forbidden");
    return NULL;
  }
  if (event->data.scalar.style == YAML_PLAIN_SCALAR_STYLE) {
    if (value[0] == '\0') {
      spsv_fail(reader, event->start_mark,
                "empty plain YAML scalars are forbidden");
      return NULL;
    }
    if (spsv_scalar_is_null(value)) {
      spsv_fail(reader, event->start_mark, "YAML null values are forbidden");
      return NULL;
    }
    if (strcmp(value, "true") == 0 || strcmp(value, "false") == 0) {
      node = spsv_new_node(reader, SPSV_NODE_BOOL, event->start_mark);
      if (node) node->as.boolean = strcmp(value, "true") == 0;
      return node;
    }
    if (spsv_scalar_integer(value, &integer)) {
      node = spsv_new_node(reader, SPSV_NODE_INTEGER, event->start_mark);
      if (node) node->as.integer = integer;
      return node;
    }
    if (spsv_has_forbidden_numeric_shape(value)) {
      spsv_fail(reader, event->start_mark,
                "floating-point and non-canonical numeric scalars are forbidden");
      return NULL;
    }
  }
  node = spsv_new_node(reader, SPSV_NODE_STRING, event->start_mark);
  if (!node) return NULL;
  node->as.string = spsv_strdup(value);
  if (!node->as.string) {
    reader->out_of_memory = 1;
    spsv_fail(reader, event->start_mark, "out of memory");
    spsv_node_destroy(node);
    return NULL;
  }
  return node;
}

int spsv_parse_yaml(const uint8_t *bytes, size_t size, spsv_node **out_root,
                    spsv_parse_error *out_error) {
  spsv_yaml_reader reader;
  yaml_event_t event;
  spsv_node *root = NULL;
  if (!bytes || !out_root || !out_error || size == 0) return 0;
  memset(&reader, 0, sizeof(reader));
  memset(out_error, 0, sizeof(*out_error));
  *out_root = NULL;
  reader.error = out_error;
  if (size > SPSV_MAX_INPUT) {
    out_error->message = spsv_strdup("input exceeds 4 MiB limit");
    return out_error->message ? 0 : -1;
  }
  if (size >= 3 && bytes[0] == 0xef && bytes[1] == 0xbb &&
      bytes[2] == 0xbf) {
    out_error->message = spsv_strdup("UTF-8 BOM is forbidden");
    return out_error->message ? 0 : -1;
  }
  if (!yaml_parser_initialize(&reader.parser)) {
    out_error->message = spsv_strdup("could not initialize libyaml");
    return -1;
  }
  yaml_parser_set_input_string(&reader.parser, bytes, size);
#define SPSV_EXPECT_EVENT(kind, message)                                      \
  do {                                                                        \
    if (!yaml_parser_parse(&reader.parser, &event)) {                         \
      spsv_parser_fail(&reader);                                               \
      goto done;                                                              \
    }                                                                         \
    if (event.type != (kind)) {                                               \
      spsv_fail(&reader, event.start_mark, (message));                        \
      yaml_event_delete(&event);                                              \
      goto done;                                                              \
    }                                                                         \
    yaml_event_delete(&event);                                                \
  } while (0)
  SPSV_EXPECT_EVENT(YAML_STREAM_START_EVENT, "expected YAML stream");
  SPSV_EXPECT_EVENT(YAML_DOCUMENT_START_EVENT, "expected one YAML document");
  if (!yaml_parser_parse(&reader.parser, &event)) {
    spsv_parser_fail(&reader);
    goto done;
  }
  root = spsv_parse_node(&reader, &event, 0);
  yaml_event_delete(&event);
  if (!root) goto done;
  SPSV_EXPECT_EVENT(YAML_DOCUMENT_END_EVENT, "expected end of YAML document");
  SPSV_EXPECT_EVENT(YAML_STREAM_END_EVENT, "multiple YAML documents are forbidden");
  *out_root = root;
  root = NULL;
#undef SPSV_EXPECT_EVENT
done:
  spsv_node_destroy(root);
  yaml_parser_delete(&reader.parser);
  return reader.out_of_memory ? -1 : (*out_root ? 1 : 0);
}

const spsv_node *spsv_map_get(const spsv_node *map, const char *key) {
  size_t i;
  if (!map || map->kind != SPSV_NODE_MAPPING) return NULL;
  for (i = 0; i < map->as.mapping.count; ++i)
    if (strcmp(map->as.mapping.items[i].key, key) == 0)
      return map->as.mapping.items[i].value;
  return NULL;
}

int spsv_map_has_only(const spsv_node *map, const char *const *keys,
                      size_t key_count, const char **out_bad_key) {
  size_t i, j;
  if (!map || map->kind != SPSV_NODE_MAPPING) return 0;
  for (i = 0; i < map->as.mapping.count; ++i) {
    int found = 0;
    for (j = 0; j < key_count; ++j)
      if (strcmp(map->as.mapping.items[i].key, keys[j]) == 0) found = 1;
    if (!found) {
      if (out_bad_key) *out_bad_key = map->as.mapping.items[i].key;
      return 0;
    }
  }
  return 1;
}

int spsv_node_equal(const spsv_node *left, const spsv_node *right) {
  size_t i;
  if (!left || !right || left->kind != right->kind) return 0;
  switch (left->kind) {
  case SPSV_NODE_STRING:
    return strcmp(left->as.string, right->as.string) == 0;
  case SPSV_NODE_BOOL:
    return left->as.boolean == right->as.boolean;
  case SPSV_NODE_INTEGER:
    return left->as.integer == right->as.integer;
  case SPSV_NODE_SEQUENCE:
    if (left->as.sequence.count != right->as.sequence.count) return 0;
    for (i = 0; i < left->as.sequence.count; ++i)
      if (!spsv_node_equal(left->as.sequence.items[i],
                           right->as.sequence.items[i]))
        return 0;
    return 1;
  case SPSV_NODE_MAPPING:
    if (left->as.mapping.count != right->as.mapping.count) return 0;
    for (i = 0; i < left->as.mapping.count; ++i) {
      const spsv_node *other =
          spsv_map_get(right, left->as.mapping.items[i].key);
      if (!other || !spsv_node_equal(left->as.mapping.items[i].value, other))
        return 0;
    }
    return 1;
  }
  return 0;
}

static int spsv_buffer_grow(spsv_buffer *buffer, size_t add) {
  char *grown;
  size_t capacity;
  if (buffer->failed || add > SIZE_MAX - buffer->size - 1) return 0;
  if (buffer->size + add + 1 <= buffer->capacity) return 1;
  capacity = buffer->capacity ? buffer->capacity : 128;
  while (capacity < buffer->size + add + 1) {
    if (capacity > SIZE_MAX / 2) {
      buffer->failed = 1;
      return 0;
    }
    capacity *= 2;
  }
  grown = (char *)realloc(buffer->data, capacity);
  if (!grown) {
    buffer->failed = 1;
    return 0;
  }
  buffer->data = grown;
  buffer->capacity = capacity;
  return 1;
}

static void spsv_buffer_append(spsv_buffer *buffer, const char *text) {
  size_t n = strlen(text);
  if (!spsv_buffer_grow(buffer, n)) return;
  memcpy(buffer->data + buffer->size, text, n);
  buffer->size += n;
  buffer->data[buffer->size] = '\0';
}

static void spsv_buffer_json_string(spsv_buffer *buffer, const char *text) {
  const unsigned char *p = (const unsigned char *)text;
  char escaped[8];
  spsv_buffer_append(buffer, "\"");
  while (*p) {
    if (*p == '"' || *p == '\\') {
      escaped[0] = '\\';
      escaped[1] = (char)*p;
      escaped[2] = '\0';
      spsv_buffer_append(buffer, escaped);
    } else if (*p < 0x20) {
      (void)snprintf(escaped, sizeof(escaped), "\\u%04x", *p);
      spsv_buffer_append(buffer, escaped);
    } else {
      escaped[0] = (char)*p;
      escaped[1] = '\0';
      spsv_buffer_append(buffer, escaped);
    }
    ++p;
  }
  spsv_buffer_append(buffer, "\"");
}

static void spsv_node_json_into(spsv_buffer *buffer, const spsv_node *node) {
  size_t i;
  char integer[64];
  switch (node->kind) {
  case SPSV_NODE_STRING:
    spsv_buffer_json_string(buffer, node->as.string);
    break;
  case SPSV_NODE_BOOL:
    spsv_buffer_append(buffer, node->as.boolean ? "true" : "false");
    break;
  case SPSV_NODE_INTEGER:
    (void)snprintf(integer, sizeof(integer), "%lld",
                   (long long)node->as.integer);
    spsv_buffer_append(buffer, integer);
    break;
  case SPSV_NODE_SEQUENCE:
    spsv_buffer_append(buffer, "[");
    for (i = 0; i < node->as.sequence.count; ++i) {
      if (i) spsv_buffer_append(buffer, ",");
      spsv_node_json_into(buffer, node->as.sequence.items[i]);
    }
    spsv_buffer_append(buffer, "]");
    break;
  case SPSV_NODE_MAPPING:
    spsv_buffer_append(buffer, "{");
    for (i = 0; i < node->as.mapping.count; ++i) {
      if (i) spsv_buffer_append(buffer, ",");
      spsv_buffer_json_string(buffer, node->as.mapping.items[i].key);
      spsv_buffer_append(buffer, ":");
      spsv_node_json_into(buffer, node->as.mapping.items[i].value);
    }
    spsv_buffer_append(buffer, "}");
    break;
  }
}

char *spsv_node_json(const spsv_node *node) {
  spsv_buffer buffer;
  memset(&buffer, 0, sizeof(buffer));
  if (!node) return spsv_strdup("{\"tag\":\"Missing\"}");
  spsv_node_json_into(&buffer, node);
  if (buffer.failed) {
    free(buffer.data);
    return NULL;
  }
  if (!buffer.data) return spsv_strdup("");
  return buffer.data;
}

char *spsv_path_join(const char *left, const char *right) {
  size_t a = strlen(left), b = 0, i;
  char *out;
  for (i = 0; right[i]; ++i) {
    if (right[i] == '~' || right[i] == '/') {
      if (b > SIZE_MAX - 2) return NULL;
      b += 2;
    } else {
      if (b == SIZE_MAX) return NULL;
      ++b;
    }
  }
  if (a > SIZE_MAX - b - 2) return NULL;
  out = (char *)malloc(a + b + 2);
  if (!out) return NULL;
  memcpy(out, left, a);
  out[a] = '/';
  b = a + 1;
  for (i = 0; right[i]; ++i) {
    if (right[i] == '~') {
      out[b++] = '~';
      out[b++] = '0';
    } else if (right[i] == '/') {
      out[b++] = '~';
      out[b++] = '1';
    } else {
      out[b++] = right[i];
    }
  }
  out[b] = '\0';
  return out;
}

int spsv_is_sha256(const spsv_node *node) {
  size_t i;
  if (!node || node->kind != SPSV_NODE_STRING ||
      strlen(node->as.string) != 64)
    return 0;
  for (i = 0; i < 64; ++i)
    if (!((node->as.string[i] >= '0' && node->as.string[i] <= '9') ||
          (node->as.string[i] >= 'a' && node->as.string[i] <= 'f')))
      return 0;
  return 1;
}
