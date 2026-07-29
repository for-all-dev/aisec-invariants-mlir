# docs/

`index.html` is the project page: the threat model, the dialect graph of six MLIR compilers, which
lowerings break constant-time, and what closing each gap would cost. It is one self-contained file —
no build step, no external requests — and it is **generated**, never edited by hand:

```bash
cd prototypes/fcvd_ct
uv run python artifact/collect.py --standalone > ../../docs/index.html
```

The generator reads the compiler descriptors in `prototypes/fcvd_ct/compilers/`, scans each
compiler's own test corpus for the operations it uses, and re-runs and times every macro-template on
the way, so the page cannot drift from the repository. Regenerate it whenever the templates or the
descriptors change.

To serve it: **Settings → Pages → Deploy from a branch → `master` / `/docs`**.
