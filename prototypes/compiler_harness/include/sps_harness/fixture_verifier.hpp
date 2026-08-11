#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

#include "sps_harness/fixture_verifier.h"

namespace sps::harness {

struct bytes_view {
  const std::uint8_t *data;
  std::size_t size;
  bytes_view(const void *p, std::size_t n) noexcept
      : data(static_cast<const std::uint8_t *>(p)), size(n) {}
  explicit bytes_view(std::string_view s) noexcept : bytes_view(s.data(), s.size()) {}
};

class api_error : public std::runtime_error {
public:
  api_error(sps_fixture_status status, const char *what)
      : std::runtime_error(what), status_(status) {}
  sps_fixture_status status() const noexcept { return status_; }
private:
  sps_fixture_status status_;
};

inline std::string_view as_string_view(sps_fixture_text_view v) noexcept {
  return {v.data ? v.data : "", v.size};
}

class result;

class actual {
public:
  static actual derive(bytes_view trace) {
    sps_fixture_actual *p = nullptr;
    auto st = sps_fixture_derive_trace(trace.data, trace.size, &p);
    if (st != SPS_FIXTURE_STATUS_OK) throw api_error(st, "trace derivation failed");
    return actual(p);
  }
  actual(actual &&o) noexcept : handle_(std::exchange(o.handle_, nullptr)) {}
  actual &operator=(actual &&o) noexcept {
    if (this != &o) {
      sps_fixture_actual_destroy(handle_);
      handle_ = std::exchange(o.handle_, nullptr);
    }
    return *this;
  }
  actual(const actual &) = delete;
  actual &operator=(const actual &) = delete;
  ~actual() { sps_fixture_actual_destroy(handle_); }
  bool valid() const {
    sps_fixture_actual_view v{};
    auto st = sps_fixture_actual_get_view(handle_, &v);
    if (st != SPS_FIXTURE_STATUS_OK) throw api_error(st, "actual view failed");
    return v.state == SPS_FIXTURE_ACTUAL_DERIVED;
  }
  sps_fixture_actual_view view() const {
    sps_fixture_actual_view v{};
    auto st = sps_fixture_actual_get_view(handle_, &v);
    if (st != SPS_FIXTURE_STATUS_OK) throw api_error(st, "actual view failed");
    return v;
  }
  std::size_t issue_count() const noexcept {
    return sps_fixture_actual_issue_count(handle_);
  }
  sps_fixture_issue_view issue(std::size_t i) const {
    sps_fixture_issue_view v{};
    auto st = sps_fixture_actual_issue_at(handle_, i, &v);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "issue index out of range");
    return v;
  }
  std::size_t event_count() const noexcept {
    return sps_fixture_actual_event_count(handle_);
  }
  sps_fixture_event_view event(std::size_t i) const {
    sps_fixture_event_view v{};
    auto st = sps_fixture_actual_event_at(handle_, i, &v);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "event index out of range");
    return v;
  }
  const sps_fixture_actual *native_handle() const noexcept { return handle_; }
private:
  explicit actual(sps_fixture_actual *p) noexcept : handle_(p) {}
  sps_fixture_actual *handle_ = nullptr;
  friend result compare(const actual &, bytes_view);
};

class result {
public:
  result(result &&o) noexcept : handle_(std::exchange(o.handle_, nullptr)) {}
  result &operator=(result &&o) noexcept {
    if (this != &o) {
      sps_fixture_result_destroy(handle_);
      handle_ = std::exchange(o.handle_, nullptr);
    }
    return *this;
  }
  result(const result &) = delete;
  result &operator=(const result &) = delete;
  ~result() { sps_fixture_result_destroy(handle_); }
  sps_fixture_comparison comparison() const {
    sps_fixture_result_view v{};
    auto st = sps_fixture_result_get_view(handle_, &v);
    if (st != SPS_FIXTURE_STATUS_OK) throw api_error(st, "result view failed");
    return v.comparison;
  }
  sps_fixture_result_view view() const {
    sps_fixture_result_view v{};
    auto st = sps_fixture_result_get_view(handle_, &v);
    if (st != SPS_FIXTURE_STATUS_OK) throw api_error(st, "result view failed");
    return v;
  }
  std::size_t issue_count() const noexcept {
    return sps_fixture_result_issue_count(handle_);
  }
  sps_fixture_issue_view issue(std::size_t i) const {
    sps_fixture_issue_view v{};
    auto st = sps_fixture_result_issue_at(handle_, i, &v);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "issue index out of range");
    return v;
  }
  std::size_t pipeline_count() const noexcept {
    return sps_fixture_result_pipeline_count(handle_);
  }
  sps_fixture_pipeline_view pipeline(std::size_t i) const {
    sps_fixture_pipeline_view v{};
    auto st = sps_fixture_result_pipeline_at(handle_, i, &v);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "pipeline index out of range");
    return v;
  }
  std::size_t consumption_count() const noexcept {
    return sps_fixture_result_consumption_count(handle_);
  }
  sps_fixture_consumption_view consumption(std::size_t i) const {
    sps_fixture_consumption_view v{};
    auto st = sps_fixture_result_consumption_at(handle_, i, &v);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "consumption index out of range");
    return v;
  }
  const sps_fixture_result *native_handle() const noexcept { return handle_; }
  std::string json() const {
    std::size_t n = 0;
    auto st = sps_fixture_result_write_json(handle_, nullptr, 0, &n);
    if (st != SPS_FIXTURE_STATUS_BUFFER_TOO_SMALL &&
        st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "JSON size query failed");
    std::string out(n, '\0');
    st = sps_fixture_result_write_json(handle_, out.data(), out.size(), &n);
    if (st != SPS_FIXTURE_STATUS_OK)
      throw api_error(st, "JSON serialization failed");
    return out;
  }
private:
  explicit result(sps_fixture_result *p) noexcept : handle_(p) {}
  sps_fixture_result *handle_ = nullptr;
  friend result compare(const actual &, bytes_view);
};

inline result compare(const actual &a, bytes_view snapshot) {
  sps_fixture_result *p = nullptr;
  auto st =
      sps_fixture_compare_snapshot(a.handle_, snapshot.data, snapshot.size, &p);
  if (st != SPS_FIXTURE_STATUS_OK)
    throw api_error(st, "snapshot comparison failed");
  return result(p);
}

} // namespace sps::harness
