#!/usr/bin/env bash
#
# measurement-rig.sh — prepare a Linux host for low-noise microarchitectural
# side-channel measurement, then put it back.
#
# The whole point of this script is legibility: every knob it touches closes a
# *specific* OS-level noise channel, and each is tagged with the reason. If you
# can read this file top to bottom and see why each line is here, you understand
# the measurement environment — which is exactly the background the profiling
# task needs.
#
# Two classes of knob:
#   RUNTIME  — settable now via sysfs/procfs; this script sets and restores them.
#   BOOT     — only settable on the kernel command line; this script AUDITS them
#              and prints the exact cmdline to add. It cannot set them at runtime,
#              and it does not pretend to.
#
# Usage:
#   sudo ./measurement-rig.sh setup   <core>   # isolate <core> for measurement
#   sudo ./measurement-rig.sh restore          # revert everything setup changed
#        ./measurement-rig.sh status  [core]   # show current state + rationale
#        ./measurement-rig.sh check   [core]   # exit 0 iff rig looks measurement-ready
#
# Restore uses a state file written at setup time, so it reverts to the exact
# prior values rather than guessing. A reboot also clears every runtime knob.
#
# Tested target: Linux, Intel or AMD x86. Missing sysfs paths are skipped with a
# warning, never a hard failure — kernels differ.

set -euo pipefail

STATE_FILE="${MRIG_STATE_FILE:-/var/tmp/measurement-rig.state}"
PROG="$(basename "$0")"

# ------------------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------------------
c_reset=$'\033[0m'; c_dim=$'\033[2m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_red=$'\033[31m'; c_bld=$'\033[1m'
log()  { printf '%s[rig]%s %s\n'  "$c_dim" "$c_reset" "$*"; }
ok()   { printf '%s[ ok ]%s %s\n' "$c_grn" "$c_reset" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$c_yel" "$c_reset" "$*" >&2; }
err()  { printf '%s[fail]%s %s\n' "$c_red" "$c_reset" "$*" >&2; }
why()  { printf '       %s· %s%s\n' "$c_dim" "$*" "$c_reset"; }

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    err "'$1' needs root (it writes to sysfs/procfs). Re-run with sudo."
    exit 1
  fi
}

# Read a sysfs/proc file if it exists; print nothing (rc 1) if it doesn't.
rd() { [[ -r "$1" ]] && tr -d '\n' < "$1" || return 1; }

# Write a value to a sysfs/proc file, tolerating absence. Returns 1 if skipped.
wr() {
  local path="$1" val="$2"
  if [[ ! -e "$path" ]]; then warn "skip (absent): $path"; return 1; fi
  if [[ ! -w "$path" ]]; then warn "skip (readonly): $path"; return 1; fi
  echo "$val" > "$path" 2>/dev/null || { warn "skip (write failed): $path"; return 1; }
  return 0
}

# Append a "key=value" line to the state file for later restore.
save() { printf '%s=%s\n' "$1" "$2" >> "$STATE_FILE"; }

# Pull a saved value back out of the state file (last occurrence wins).
saved() { grep -E "^$1=" "$STATE_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- || true; }

# ------------------------------------------------------------------------------
# Topology
# ------------------------------------------------------------------------------
# Resolve the SMT sibling(s) of a core from the kernel's own topology view.
# thread_siblings_list looks like "2,14" or "2-3"; we return every listed
# logical CPU that is not CORE itself.
siblings_of() {
  local core="$1" f="/sys/devices/system/cpu/cpu$1/topology/thread_siblings_list"
  local list; list="$(rd "$f" || true)"
  [[ -z "$list" ]] && return 0
  # expand ranges and commas
  local expanded=()
  IFS=',' read -ra parts <<< "$list"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then
      local a="${p%-*}" b="${p#*-}"
      for ((i=a;i<=b;i++)); do expanded+=("$i"); done
    else
      expanded+=("$p")
    fi
  done
  for c in "${expanded[@]}"; do [[ "$c" != "$core" ]] && echo "$c"; done
}

# ------------------------------------------------------------------------------
# SETUP
# ------------------------------------------------------------------------------
do_setup() {
  need_root setup
  local core="${1:-}"
  if [[ -z "$core" ]]; then
    err "usage: $PROG setup <core>   (the logical CPU you will pin the victim to)"
    exit 1
  fi
  if [[ ! -e "/sys/devices/system/cpu/cpu$core" ]]; then
    err "cpu$core does not exist."
    exit 1
  fi

  if [[ -f "$STATE_FILE" ]]; then
    warn "state file $STATE_FILE already exists — a rig may already be active."
    warn "run '$PROG restore' first, or remove the file. Refusing to stack changes."
    exit 1
  fi
  : > "$STATE_FILE"
  save MEASUREMENT_CORE "$core"
  log "isolating cpu$core for measurement. prior state -> $STATE_FILE"
  echo

  # --- 1. SMT sibling: offline it ---------------------------------------------
  # A hyperthread shares L1/L2 and execution ports with its sibling. A neighbour
  # running on the sibling is either your channel (if that's the attacker) or
  # pure contamination (if it isn't). For a controlled victim measurement we want
  # the physical core to ourselves, so we offline the sibling logical CPU.
  local sibs; sibs="$(siblings_of "$core")"
  if [[ -n "$sibs" ]]; then
    # for s in $sibs; do
    #   local onf="/sys/devices/system/cpu/cpu$s/online"
    #   local prev; prev="$(rd "$onf" || echo 1)"
    #   save "SIBLING_ONLINE_$s" "$prev"
    #   #if wr "$onf" 0; then ok "offlined SMT sibling cpu$s of cpu$core"; why "removes L1/L2/port contention from the co-thread"; fi
    #   if timeout 5 bash -c "echo 0 > '$onf'" 2>/dev/null; then
    #     ok "offlined SMT sibling cpu$s of cpu$core"; why "removes L1/L2/port contention from the co-thread"
    #   else
    #     warn "could not offline sibling cpu$s (hotplug blocked) — continuing without it"
    #     why "measurement still valid via taskset pinning; sibling left online"
    #   fi
    # done
    for s in $sibs; do
      local onf="/sys/devices/system/cpu/cpu$s/online"
      local prev; prev="$(rd "$onf" || echo 1)"
      save "SIBLING_ONLINE_$s" "$prev"
      if timeout 5 bash -c "echo 0 > '$onf'" 2>/dev/null; then
        ok "offlined SMT sibling cpu$s of cpu$core"; why "removes L1/L2/port contention"
      else
        warn "could not offline sibling cpu$s (hotplug blocked) — continuing without it"
      fi
    done
  else
    log "cpu$core reports no SMT sibling (SMT off, or single-thread core)"
  fi

  # --- 2. Frequency governor: performance -------------------------------------
  # On-demand/schedutil governors change frequency in response to load. Frequency
  # steps rescale every cycle-count you take, so a governor transition mid-run is
  # indistinguishable from a signal. Pin to 'performance' (fixed max non-turbo).
  for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [[ -e "$g" ]] || continue
    local cpu; cpu="$(echo "$g" | grep -oE 'cpu[0-9]+' | head -n1 | tr -dc 0-9)"
    local prev; prev="$(rd "$g" || true)"
    [[ -n "$prev" ]] && save "GOV_$cpu" "$prev"
    wr "$g" performance >/dev/null || true
  done
  ok "cpufreq governor -> performance (all CPUs)"; why "stops frequency scaling from rescaling your cycle counts"

  # --- 3. Turbo / boost: off --------------------------------------------------
  # Turbo opportunistically overclocks based on thermal/power headroom, so the
  # effective clock drifts across a run as the core heats up. Disable it for a
  # flat clock. Intel pstate and generic cpufreq expose different switches.
  if [[ -e /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
    save TURBO_IFACE intel_pstate
    save TURBO_PREV "$(rd /sys/devices/system/cpu/intel_pstate/no_turbo || echo 0)"
    wr /sys/devices/system/cpu/intel_pstate/no_turbo 1 >/dev/null && ok "intel turbo -> off"
  elif [[ -e /sys/devices/system/cpu/cpufreq/boost ]]; then
    save TURBO_IFACE cpufreq_boost
    save TURBO_PREV "$(rd /sys/devices/system/cpu/cpufreq/boost || echo 1)"
    wr /sys/devices/system/cpu/cpufreq/boost 0 >/dev/null && ok "cpufreq boost -> off"
  else
    warn "no turbo/boost switch found (may be firmware-controlled)"
  fi
  why "removes clock drift as the core warms up during a run"

  # --- 4. Deep C-states on the measurement core: disabled ---------------------
  # If the core drops into a deep idle state between measurements, the C-state
  # *exit latency* on the next call adds tens to hundreds of ns of variance. We
  # disable every non-POLL idle state on the measurement core so it stays hot.
  # (nohz_full + a busy loop help too, but this is the runtime-settable part.)
  local disabled_any=0
  for st in /sys/devices/system/cpu/cpu$core/cpuidle/state[1-9]*/disable; do
    [[ -e "$st" ]] || continue
    save "CSTATE_$(echo "$st" | tr '/' '_')" "$(rd "$st" || echo 0)"
    wr "$st" 1 >/dev/null && disabled_any=1
  done
  [[ "$disabled_any" == 1 ]] && { ok "deep C-states disabled on cpu$core"; why "removes C-state exit latency from the first access after idle"; } \
                             || log "no per-core cpuidle controls (cpuidle off, or boot-pinned)"

  # --- 5. ASLR: off -----------------------------------------------------------
  # Address-space layout randomisation moves your buffers and code every run, so
  # absolute addresses (and their cache-set mapping) shift between measurements.
  # For stable set indices and reproducible Flush+Reload offsets, turn it off.
  save ASLR "$(rd /proc/sys/kernel/randomize_va_space || echo 2)"
  wr /proc/sys/kernel/randomize_va_space 0 >/dev/null && ok "ASLR -> off"; why "stabilises addresses and their cache-set mapping across runs"

  # --- 6. perf_event_paranoid + userspace rdpmc -------------------------------
  # paranoid gates access to the PMU; -1 lets an unprivileged harness open all
  # events. rdpmc=2 lets the harness read counters from userspace (via CR4.PCE)
  # without a syscall per read — essential for low-overhead per-invocation counts.
  save PARANOID "$(rd /proc/sys/kernel/perf_event_paranoid || echo 2)"
  wr /proc/sys/kernel/perf_event_paranoid -1 >/dev/null && ok "perf_event_paranoid -> -1"; why "lets the measurement harness open PMU events directly"
  if [[ -e /sys/bus/event_source/devices/cpu/rdpmc ]]; then
    save RDPMC "$(rd /sys/bus/event_source/devices/cpu/rdpmc || echo 1)"
    wr /sys/bus/event_source/devices/cpu/rdpmc 2 >/dev/null && ok "userspace rdpmc -> enabled"; why "counter reads without a syscall per read (lower measurement overhead)"
  fi

  # --- 7. NMI watchdog: off ---------------------------------------------------
  # The NMI watchdog fires a periodic non-maskable interrupt on every CPU. An NMI
  # in the middle of a measured region is a large, periodic perturbation. Off.
  save NMI_WATCHDOG "$(rd /proc/sys/kernel/nmi_watchdog || echo 1)"
  wr /proc/sys/kernel/nmi_watchdog 0 >/dev/null && ok "nmi_watchdog -> off"; why "removes a periodic NMI perturbation from the measured region"

  # --- 8. Automatic NUMA balancing: off ---------------------------------------
  # Auto-NUMA migrates pages and threads to 'improve' locality. Mid-run migration
  # relocates your working set and your thread — noise that looks like a signal.
  if [[ -e /proc/sys/kernel/numa_balancing ]]; then
    save NUMA_BALANCING "$(rd /proc/sys/kernel/numa_balancing || echo 0)"
    wr /proc/sys/kernel/numa_balancing 0 >/dev/null && ok "numa_balancing -> off"; why "stops the kernel migrating your pages/thread mid-run"
  fi

  # --- 9. KSM (kernel same-page merging): off ---------------------------------
  # KSM dedups identical pages across processes/VMs into one physical page. That
  # shared page is precisely what makes cross-process Flush+Reload possible. For a
  # *controlled* victim rig you usually want it OFF so your address map is honest;
  # flip it on deliberately only if dedup is the channel you are studying.
  if [[ -e /sys/kernel/mm/ksm/run ]]; then
    save KSM "$(rd /sys/kernel/mm/ksm/run || echo 0)"
    wr /sys/kernel/mm/ksm/run 0 >/dev/null && ok "KSM -> off"; why "removes cross-process page dedup (the basis of Flush+Reload) unless you want it"
  fi

  # --- 10. Transparent Huge Pages: never --------------------------------------
  # THP silently backs regions with 2 MiB pages, which changes physical layout and
  # cache-set mapping nondeterministically between runs. Set 'never' for stable,
  # 4 KiB-granular addressing (use explicit hugetlb if you actually want 2 MiB).
  if [[ -e /sys/kernel/mm/transparent_hugepage/enabled ]]; then
    local cur; cur="$(rd /sys/kernel/mm/transparent_hugepage/enabled || true)"
    # extract the [bracketed] current value
    cur="$(echo "$cur" | grep -oE '\[[a-z]+\]' | tr -d '[]' || echo madvise)"
    save THP "${cur:-madvise}"
    wr /sys/kernel/mm/transparent_hugepage/enabled never >/dev/null && ok "THP -> never"; why "stable 4 KiB layout and cache-set mapping across runs"
  fi

  # --- 11. IRQ affinity: move interrupts off the measurement core -------------
  # A device interrupt delivered to the measurement core lands right in the middle
  # of a measured region. Steer IRQ handling to the other cores. We save each IRQ's
  # prior affinity so restore is exact; some IRQs refuse a move (managed/percpu),
  # which is fine — best effort.
  local nproc_total; nproc_total="$(nproc --all 2>/dev/null || echo 1)"
  # build a hex CPU mask of every online CPU except the measurement core
  local mask_dec=0 c
  for ((c=0;c<nproc_total;c++)); do
    [[ "$c" == "$core" ]] && continue
    [[ "$(rd /sys/devices/system/cpu/cpu$c/online 2>/dev/null || echo 1)" == 0 ]] && continue
    mask_dec=$(( mask_dec | (1 << c) ))
  done
  local mask_hex; mask_hex="$(printf '%x' "$mask_dec")"
  if [[ "$mask_dec" -ne 0 ]]; then
    local moved=0
    for aff in /proc/irq/*/smp_affinity; do
      [[ -w "$aff" ]] || continue
      local irq; irq="$(echo "$aff" | grep -oE '[0-9]+' | head -n1)"
      local prev; prev="$(rd "$aff" || true)"
      [[ -n "$prev" ]] && save "IRQ_$irq" "$prev"
      echo "$mask_hex" > "$aff" 2>/dev/null && moved=$((moved+1)) || true
    done
    if [[ -w /proc/irq/default_smp_affinity ]]; then
      save IRQ_DEFAULT "$(rd /proc/irq/default_smp_affinity || true)"
      echo "$mask_hex" > /proc/irq/default_smp_affinity 2>/dev/null || true
    fi
    ok "steered $moved IRQs away from cpu$core (mask 0x$mask_hex)"; why "keeps device interrupts out of the measured region"
  fi

  echo
  ok "runtime isolation applied for cpu$core."
  audit_boot "$core"
  echo
  log "when done:  sudo $PROG restore"
}

# ------------------------------------------------------------------------------
# BOOT-PARAM AUDIT (cannot be set at runtime — we detect and instruct)
# ------------------------------------------------------------------------------
audit_boot() {
  local core="${1:-}"
  echo
  printf '%s── boot-time knobs (kernel cmdline — not settable at runtime) ──%s\n' "$c_bld" "$c_reset"
  local cmdline; cmdline="$(rd /proc/cmdline || echo '')"
  local want=(isolcpus nohz_full rcu_nocbs)
  local missing=()
  for k in "${want[@]}"; do
    if echo "$cmdline" | grep -qw -- "$k"; then
      local val; val="$(echo "$cmdline" | grep -oE "${k}[= ][^ ]*" | head -n1)"
      if [[ -n "$core" ]] && ! echo "$val" | grep -qw "$core"; then
        warn "$k present but does not list core $core: $val"
      else
        ok "$k present: $val"
      fi
    else
      missing+=("$k")
    fi
  done
  # C-state ceiling
  if echo "$cmdline" | grep -qE 'intel_idle.max_cstate|processor.max_cstate'; then
    ok "C-state ceiling present on cmdline"
  else
    missing+=("processor.max_cstate=1")
  fi

  if [[ "${#missing[@]}" -gt 0 ]]; then
    warn "missing boot isolation: ${missing[*]}"
    why "isolcpus:  removes the core from the scheduler's load balancer"
    why "nohz_full: stops the periodic timer tick on the core (biggest single win)"
    why "rcu_nocbs: offloads RCU callback processing off the core"
    why "max_cstate=1: firmware never parks the core in a deep sleep state"
    echo
    printf '   %sadd to GRUB_CMDLINE_LINUX and re-run update-grub, then reboot:%s\n' "$c_bld" "$c_reset"
    printf '   isolcpus=%s nohz_full=%s rcu_nocbs=%s processor.max_cstate=1 intel_idle.max_cstate=1\n' \
           "${core:-N}" "${core:-N}" "${core:-N}"
  fi
}

# ------------------------------------------------------------------------------
# RESTORE
# ------------------------------------------------------------------------------
do_restore() {
  need_root restore
  if [[ ! -f "$STATE_FILE" ]]; then
    err "no state file at $STATE_FILE — nothing to restore (a reboot also clears everything)."
    exit 1
  fi
  log "restoring from $STATE_FILE"

  # governors
  while IFS='=' read -r k v; do
    case "$k" in
      GOV_*)   wr "/sys/devices/system/cpu/cpu${k#GOV_}/cpufreq/scaling_governor" "$v" >/dev/null || true ;;
      SIBLING_ONLINE_*) wr "/sys/devices/system/cpu/cpu${k#SIBLING_ONLINE_}/online" "$v" >/dev/null || true ;;
      CSTATE_*) local p="${k#CSTATE_}"; p="${p//_//}"; wr "/$p" "$v" >/dev/null || true ;;
      IRQ_DEFAULT) wr /proc/irq/default_smp_affinity "$v" >/dev/null || true ;;
      IRQ_*)   wr "/proc/irq/${k#IRQ_}/smp_affinity" "$v" >/dev/null || true ;;
    esac
  done < "$STATE_FILE"

  # scalars
  local iface
  iface="$(saved TURBO_IFACE)"
  case "$iface" in
    intel_pstate)  wr /sys/devices/system/cpu/intel_pstate/no_turbo "$(saved TURBO_PREV)" >/dev/null || true ;;
    cpufreq_boost) wr /sys/devices/system/cpu/cpufreq/boost "$(saved TURBO_PREV)" >/dev/null || true ;;
  esac
  [[ -n "$(saved ASLR)" ]]          && wr /proc/sys/kernel/randomize_va_space "$(saved ASLR)" >/dev/null || true
  [[ -n "$(saved PARANOID)" ]]      && wr /proc/sys/kernel/perf_event_paranoid "$(saved PARANOID)" >/dev/null || true
  [[ -n "$(saved RDPMC)" ]]         && wr /sys/bus/event_source/devices/cpu/rdpmc "$(saved RDPMC)" >/dev/null || true
  [[ -n "$(saved NMI_WATCHDOG)" ]]  && wr /proc/sys/kernel/nmi_watchdog "$(saved NMI_WATCHDOG)" >/dev/null || true
  [[ -n "$(saved NUMA_BALANCING)" ]]&& wr /proc/sys/kernel/numa_balancing "$(saved NUMA_BALANCING)" >/dev/null || true
  [[ -n "$(saved KSM)" ]]           && wr /sys/kernel/mm/ksm/run "$(saved KSM)" >/dev/null || true
  [[ -n "$(saved THP)" ]]           && wr /sys/kernel/mm/transparent_hugepage/enabled "$(saved THP)" >/dev/null || true

  rm -f "$STATE_FILE"
  ok "restored. (boot-cmdline knobs, if you added any, still require removing them from GRUB.)"
}

# ------------------------------------------------------------------------------
# STATUS / CHECK
# ------------------------------------------------------------------------------
# Print one status row and update READY in the *current* shell (no subshell).
# field <label> <value> <want> [note]
field() {
  local label="$1" val="$2" want="$3" note="${4:-}" color="$c_grn"
  if [[ "$val" != "$want" ]]; then color="$c_yel"; READY=1; fi
  printf '  %-26s %s%s%s%s\n' "$label" "$color" "$val" "$c_reset" "${note:+   $note}"
}

do_status() {
  local core="${1:-}"
  READY=0
  printf '%smeasurement-rig status%s\n' "$c_bld" "$c_reset"
  [[ -f "$STATE_FILE" ]] && log "active rig state file present ($STATE_FILE), core=$(saved MEASUREMENT_CORE)" \
                         || log "no active rig state file (runtime knobs at their defaults)"
  echo

  local v
  v="$(rd /sys/devices/system/cpu/smt/control 2>/dev/null || echo n/a)"
  [[ "$v" == n/a || "$v" == notsupported ]] || field "SMT control" "$v" off "(want off, or sibling offlined)"
  v="$(rd /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo n/a)"
  field "governor (cpu0)"      "$v" performance
  if [[ -e /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
    field "intel no_turbo" "$(rd /sys/devices/system/cpu/intel_pstate/no_turbo)" 1 "(want 1)"
  elif [[ -e /sys/devices/system/cpu/cpufreq/boost ]]; then
    field "cpufreq boost" "$(rd /sys/devices/system/cpu/cpufreq/boost)" 0 "(want 0)"
  fi
  field "ASLR"                 "$(rd /proc/sys/kernel/randomize_va_space 2>/dev/null || echo n/a)" 0 "(want 0)"
  field "perf_event_paranoid"  "$(rd /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo n/a)" -1 "(want -1)"
  field "nmi_watchdog"         "$(rd /proc/sys/kernel/nmi_watchdog 2>/dev/null || echo n/a)" 0 "(want 0)"
  v="$(rd /proc/sys/kernel/numa_balancing 2>/dev/null || echo n/a)"
  [[ "$v" != n/a ]] && field "numa_balancing" "$v" 0 "(want 0)"
  v="$(rd /sys/kernel/mm/ksm/run 2>/dev/null || echo n/a)"
  [[ "$v" != n/a ]] && field "KSM run" "$v" 0 "(want 0 for a controlled rig)"
  v="$(rd /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | grep -oE '\[[a-z]+\]' | tr -d '[]' || echo n/a)"
  [[ "$v" != n/a ]] && field "THP" "$v" never "(want never)"

  echo
  audit_boot "$core"
  echo
  if [[ "$READY" -eq 0 ]]; then ok "runtime knobs look measurement-ready"; else warn "some runtime knobs are not in the low-noise position (see yellow)"; fi
}

do_check() {
  # Quiet-ish: run status, exit nonzero if not ready. Useful as a harness preflight.
  do_status "${1:-}" >/tmp/.mrig_status 2>&1 || true
  if grep -q 'not in the low-noise position' /tmp/.mrig_status; then
    cat /tmp/.mrig_status; err "rig not ready"; exit 1
  fi
  cat /tmp/.mrig_status
  exit 0
}

# ------------------------------------------------------------------------------
usage() {
  cat <<EOF
${PROG} — prepare/restore a low-noise side-channel measurement rig.

  sudo ${PROG} setup   <core>    isolate logical CPU <core> for the victim
  sudo ${PROG} restore           revert everything setup changed (exact prior values)
       ${PROG} status  [core]    show every knob's current state + rationale
       ${PROG} check   [core]    exit 0 iff the runtime knobs are measurement-ready

State file: ${STATE_FILE}   (override with \$MRIG_STATE_FILE)
Boot-time knobs (isolcpus/nohz_full/rcu_nocbs/max_cstate) are audited, not set —
the script prints the exact cmdline to add.
EOF
}

case "${1:-}" in
  setup)   shift; do_setup "${1:-}" ;;
  restore) do_restore ;;
  status)  shift || true; do_status "${1:-}" ;;
  check)   shift || true; do_check  "${1:-}" ;;
  ""|-h|--help|help) usage ;;
  *) err "unknown command: $1"; echo; usage; exit 1 ;;
esac