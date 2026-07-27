"""Minimal channel-7/8 detector: forward taint from sps.label="high" to
sps.sink_class="public" stores. No relational reasoning at all.
Runs on mlir-opt output (names already discarded -> uses %argN / %N)."""
import re, subprocess, sys, glob, os
MLIR_OPT = "/opt/homebrew/opt/llvm/bin/mlir-opt"

def analyze(path):
    ir = subprocess.run([MLIR_OPT, path], capture_output=True, text=True).stdout
    if not ir: return None
    tainted = set()
    # seed: block args carrying sps.label = "high"
    for m in re.finditer(r'(%arg\d+)\s*:\s*[^,)]*?\{[^}]*sps\.label\s*=\s*"high"', ir):
        tainted.add(m.group(1))
    if not tainted: return ("NO-POLICY", [])
    findings = []
    # fixpoint forward propagation over "%r = op operands..."
    for _ in range(10):
        for line in ir.splitlines():
            m = re.match(r'\s*(%\d+)\s*=\s*(\S+)(.*)', line)
            if not m: continue
            res, ops = m.group(1), set(re.findall(r'%\w+', m.group(3)))
            if ops & tainted: tainted.add(res)
    # sinks: stores whose *stored value* is tainted and target is public
    for i, line in enumerate(ir.splitlines(), 1):
        s = re.match(r'\s*llvm\.store\s+(%\w+),\s*(%\w+)(.*)', line)
        if not s: continue
        val, tgt, rest = s.group(1), s.group(2), s.group(3)
        if val in tainted and 'sps.sink_class = "public"' in rest:
            findings.append((i, "secret-to-public-sink", line.strip()))
    return ("OK", findings)

for f in sorted(glob.glob(sys.argv[1] + "/*.mlir")):
    r = analyze(f)
    if r is None: print(f"  PARSE-FAIL {os.path.basename(f)}"); continue
    status, finds = r
    if status == "NO-POLICY": continue
    tag = "LEAK" if finds else "clean"
    print(f"{tag:6} {os.path.basename(f)}" + (f"  -> line {finds[0][0]}: {finds[0][2][:70]}" if finds else ""))
