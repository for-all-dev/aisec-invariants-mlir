"""Rebuild the translation-map artifact from live data.

    uv run python artifact/collect.py > artifact/translation-map.html

Everything the page shows is produced here: the dialect graph is the union of the
pipeline steps in `compilers/*.json`, the operation tables come from the same corpus
scan `fcvd-ct-coverage` uses, and every template is re-run and timed. Nothing in the
page is typed in by hand except the prose and the layer assignment below.
"""
import json, time
from pathlib import Path
from fcvdct.context import make_context
from fcvdct.coverage import COMPILERS, TEMPLATES, Compiler, report
from fcvdct.structural import check_lowering
from xdsl.parser import Parser

# Layers are assigned by hand: they encode how far a dialect is from the source
# language, which is a judgement about MLIR, not something the data knows.
LAYER = {
    "onnx": 0, "secret": 0, "tensor_ext": 0, "polynomial": 0,
    "krnl": 1, "tensor": 1, "mod_arith": 1,
    "affine": 2,
    "scf": 3, "memref": 3,
    "cf": 4, "arith": 4, "vector": 4, "func": 4,
    "handshake": 5, "calyx": 5, "dc": 5,
    "hw": 6, "comb": 6, "seq": 6,
    "llvm": 7, "sv": 7, "verilog": 7,
}

data = {"compilers": [], "dialects": {}, "steps": [], "templates": [], "modules": []}
ctx = make_context()

for path in sorted(COMPILERS.glob("*.json")):
    c = Compiler.load(path)
    r = report(c, prove=True, timeout=120)
    data["compilers"].append({
        "name": c.name, "commit": c.commit, "repo": c.repo, "note": c.note,
        "files": r.files_scanned,
        "distinct": len(r.operations), "mentions": sum(o.occurrences for o in r.operations),
        "form0": len(r.by_form(0)), "form1": len(r.by_form(1)), "form2": len(r.by_form(2)),
        "m0": sum(o.occurrences for o in r.by_form(0)),
        "m1": sum(o.occurrences for o in r.by_form(1)),
        "m2": sum(o.occurrences for o in r.by_form(2)),
        "steps": len(r.stages),
        "specified": len([s for s in r.stages if s.proved or s.breaks]),
    })
    for op in r.operations:
        d = op.name.split(".")[0]
        entry = data["dialects"].setdefault(d, {"name": d, "compilers": [], "ops": {}})
        if c.name not in entry["compilers"]:
            entry["compilers"].append(c.name)
        # the same operation can be seen by several compilers; keep the max count
        prev = entry["ops"].get(op.name)
        if prev is None or op.occurrences > prev["n"]:
            entry["ops"][op.name] = {"n": op.occurrences, "form": op.form, "by": op.covered_by}
    for s in r.stages:
        data["steps"].append({
            "compiler": c.name, "pass": s.stage.pass_name,
            "from": list(s.stage.source_dialects), "to": list(s.stage.target_dialects),
            "cited": s.stage.cited, "forms": list(s.forms),
            "proved": list(s.proved), "breaks": list(s.breaks),
        })

# a dialect that only ever appears as a lowering *target* still needs a node
for step in data["steps"]:
    for d in step["from"] + step["to"]:
        data["dialects"].setdefault(d, {"name": d, "compilers": [], "ops": {}})
        if step["compiler"] not in data["dialects"][d]["compilers"]:
            data["dialects"][d]["compilers"].append(step["compiler"])

for d, entry in data["dialects"].items():
    ops = sorted(entry["ops"].items(), key=lambda kv: -kv[1]["n"])
    entry["ops"] = [{"name": k, **v} for k, v in ops]
    entry["forms"] = [sum(1 for o in entry["ops"] if o["form"] == f) for f in (0, 1, 2)]
    entry["mentions"] = sum(o["n"] for o in entry["ops"])
    entry["layer"] = LAYER.get(d, 4)

# measured: one timed run per template
for f in sorted(TEMPLATES.glob("*.mlir")) + sorted(TEMPLATES.glob("*/*.mlir")):
    module = Parser(ctx, f.read_text(), str(f)).parse_module()
    start = time.perf_counter()
    res = check_lowering(ctx, module, timeout=120)
    data["templates"].append({
        "file": str(f.relative_to(TEMPLATES)), "verdict": res.verdict,
        "obs": [res.n_source_observations, res.n_target_observations],
        "bounded": res.bounded, "seconds": round(time.perf_counter() - start, 3),
        "lines": len(f.read_text().splitlines()),
    })

# measured: the size of every translation we had to write ourselves
for name, what in [
    ("hw_ops.py", "hw.constant: syntax + semantics"),
    ("tensor_ops.py", "tensor.extract/insert + the tensor type, on SMT arrays"),
    ("affine_ops.py", "affine.for/yield syntax"),
    ("index_ops.py", "arith on index, arith.index_cast"),
    ("predication.py", "control flow by if-conversion and unrolling"),
    ("leakage.py", "the leakage model itself"),
    ("selfcomp.py", "self-composition driver, four obligations"),
    ("structural.py", "macro-template checker"),
    ("pdl_ct.py", "PDL rewrite checker"),
    ("coverage.py", "the coverage counter"),
]:
    p = Path("src/fcvdct") / name
    data["modules"].append({"file": name, "what": what, "lines": len(p.read_text().splitlines())})

data["dialects"] = sorted(data["dialects"].values(), key=lambda e: (e["layer"], -e["mentions"]))
template = Path(__file__).parent / "page.template.html"
print(
    template.read_text().replace(
        "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    )
)
