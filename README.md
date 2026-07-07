# Compiler security in deep learning: stream of Apart's Secure Program Synthesis Fellowship

## Research monorepo conventions

### Research notes

If you own a file (you're the primary writer), name it `./docs/research/*.<yourname>.md`. If an AI is the primary writer (and reader), call it `./docs/research/*.agents.md`. If more than one people are collaborating on it, just call it `./docs/research/*.md`

Feel free to dump pdfs of preexisting work and/or `*.<yourname|agent>.md` summary files of preexisting work in `./docs/priorlit/`.

### python dev

Make `uv` projects, avoid pip.

in every `uv` package, run `uv add --dev ruff ty pytest hypothesis`

### Subdirectories in `./prototypes`

**Feel free to make as many subdirectories as you want** we can organize later if we want to. `./prototypes/*/` will be the main day to day work, I'm expecting, unless that work is in `./docs/research/`

### Outward facing writeups in `./comms`

We won't do this for a while.

## License

This repository is licensed under the **MIT License** (see [`LICENSE`](LICENSE)), with the following exception:

- **`prototypes/initial/`** — **Apache License 2.0** (see [`prototypes/initial/LICENSE`](prototypes/initial/LICENSE))

See [`NOTICE`](NOTICE) for full details.
