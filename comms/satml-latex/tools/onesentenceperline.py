#!/usr/bin/env python3
"""Reflow LaTeX prose so that each text-mode sentence starts on its own line.

Only running text is touched.  Math (inline and display), comments, table rows,
and code-like environments (tikzpicture, tabular, verbatim, lstlisting, ...) are
copied through unchanged, and periods inside citations, references, labels,
URLs, \\texttt arguments, or after common abbreviations do not end a sentence.

Usage:
    python tools/onesentenceperline.py sections/*.tex        # rewrite in place
    python tools/onesentenceperline.py --diff sections/*.tex # preview only
    python tools/onesentenceperline.py --check sections/*.tex  # exit 1 if stale
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys

# Environments whose bodies are not running text.
SKIP_ENVS = {
    "tikzpicture", "tabular", "tabular*", "tabularx", "array",
    "verbatim", "lstlisting", "minted", "Verbatim", "alltt",
    "equation", "equation*", "align", "align*", "aligned", "gather",
    "gather*", "multline", "multline*", "displaymath", "math", "eqnarray",
    "eqnarray*", "matrix", "pmatrix", "bmatrix", "cases",
    "algorithmic", "algorithm", "IEEEkeywords", "thebibliography",
}

# Commands whose braced argument must never be split.
OPAQUE_CMDS = (
    "cite", "citep", "citet", "nocite", "ref", "eqref", "cref", "Cref",
    "autoref", "pageref", "label", "url", "href", "path", "texttt", "verb",
    "includegraphics", "includesvg", "input", "include", "bibliography",
    "bibliographystyle", "usepackage", "documentclass",
)

# A period after one of these does not end a sentence.
ABBREVIATIONS = {
    "e.g", "i.e", "cf", "etc", "vs", "resp", "approx", "ca", "viz", "al",
    "et al", "fig", "figs", "eq", "eqs", "sec", "secs", "tab", "tabs",
    "ref", "refs", "no", "nos", "pp", "vol", "ch", "chap", "app", "def",
    "thm", "lem", "prop", "cor", "st", "dr", "prof", "mr", "mrs", "ms",
    "inc", "ltd", "dept", "univ", "w.r.t", "a.k.a", "s.t", "i.i.d",
}

# Structural lines that are never joined with their neighbours.
STRUCTURAL = re.compile(
    r"\\(?:sub)*section\*?\b|\\paragraph\*?\b|\\begin\b|\\end\b|\\label\b|"
    r"\\input\b|\\include\b|\\bibliography|\\usepackage\b|\\documentclass\b|"
    r"\\newcommand\b|\\renewcommand\b|\\def\b|\\maketitle\b|\\title\b|"
    r"\\author\b|\\IEEE|\\centering\b|\\hline\b|\\toprule\b|\\midrule\b|"
    r"\\bottomrule\b|\\foreach\b|\\node\b|\\draw\b|\\fill\b|\\definecolor\b|"
    r"\\pgfmath|\\makeatletter|\\makeatother|\\thanks\b|\\small\b|\\footnotesize\b"
)

BEGIN_ENV = re.compile(r"\\begin\{([^}]*)\}")
END_ENV = re.compile(r"\\end\{([^}]*)\}")
INLINE_COMMENT = re.compile(r"(?<!\\)%")

# Sentence-final punctuation, optional closing quotes/brackets, then space.
CANDIDATE = re.compile(r"[.!?](?:''|[\"'’”)\]])*\s+")
TRAILING_WORD = re.compile(r"([A-Za-z][A-Za-z.]*)\.$")
INITIAL = re.compile(r"(?:^|[\s(\[])[A-Z]\.$")

SENTINEL = "\x00"


def _mask(text: str) -> tuple[str, list[str]]:
    """Replace math and opaque command arguments with period-free sentinels."""
    stash: list[str] = []

    def keep(match: re.Match) -> str:
        stash.append(match.group(0))
        return f"{SENTINEL}{len(stash) - 1}{SENTINEL}"

    patterns = [
        r"\\\[.*?\\\]",                       # display math
        r"\\\(.*?\\\)",                       # inline math
        r"(?<!\\)\$\$.*?(?<!\\)\$\$",         # $$ ... $$
        r"(?<!\\)\$(?:\\.|[^$\\])*(?<!\\)\$",  # $ ... $
        r"\\verb(?P<d>.).*?(?P=d)",           # \verb|...|
        r"\\(?:" + "|".join(OPAQUE_CMDS) + r")\b\*?(?:\[[^\]]*\])*(?:\{[^{}]*\})*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, keep, text, flags=re.DOTALL)
    return text, stash


def _unmask(text: str, stash: list[str]) -> str:
    return re.sub(
        f"{SENTINEL}(\\d+){SENTINEL}", lambda m: stash[int(m.group(1))], text
    )


def _starts_sentence(text: str, index: int) -> bool:
    """Could the character at `index` open a new sentence?"""
    if index >= len(text):
        return False
    char = text[index]
    if char == "\\":
        name = re.match(r"\\([A-Za-z@]+)", text[index:])
        # A stray citation or reference continues the previous sentence.
        return not (name and name.group(1).lower().rstrip("*") in OPAQUE_CMDS)
    return bool(re.match(r"[A-Z0-9(\[`\"'“]|" + SENTINEL, char))


def _is_abbreviation(prefix: str) -> bool:
    """`prefix` ends with the candidate period; decide whether it terminates."""
    if INITIAL.search(prefix):  # "J. Smith", "O. Ring"
        return True
    match = TRAILING_WORD.search(prefix)
    if not match:
        return False
    word = match.group(1).lower().strip(".")
    return word in ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    """Split one paragraph of running text into sentences."""
    masked, stash = _mask(text)
    pieces: list[str] = []
    start = 0
    for match in CANDIDATE.finditer(masked):
        cut = match.end() - len(match.group(0)) + len(match.group(0).rstrip())
        if not _starts_sentence(masked, match.end()):
            continue
        if _is_abbreviation(masked[start:cut]):
            continue
        pieces.append(masked[start:cut])
        start = match.end()
    pieces.append(masked[start:])
    return [_unmask(p, stash).strip() for p in pieces if p.strip()]


def _balanced(text: str) -> bool:
    stripped = re.sub(r"\\[{}$]", "", text)
    return (
        stripped.count("{") == stripped.count("}")
        and stripped.count("$") % 2 == 0
    )


def _is_prose(line: str) -> bool:
    """Is this line ordinary running text we may reflow?"""
    stripped = line.strip()
    if not stripped or stripped.startswith("%"):
        return False
    if INLINE_COMMENT.search(line):
        return False
    if stripped.endswith("\\\\") or "&" in stripped:  # table rows, line breaks
        return False
    if re.fullmatch(r"\\[A-Za-z@]+\*?", stripped):  # a bare command, e.g. \and
        return False
    if STRUCTURAL.match(stripped):
        return False
    return True


def reflow(source: str) -> str:
    lines = source.splitlines(keepends=True)
    newline = "\r\n" if source.endswith("\r\n") else "\n"
    out: list[str] = []
    block: list[str] = []
    env_stack: list[str] = []

    def flush() -> None:
        if not block:
            return
        indent = re.match(r"\s*", block[0]).group(0)
        joined = " ".join(line.strip() for line in block)
        # Sentences continuing an \item are indented so they do not read as items.
        hanging = indent + ("  " if joined.lstrip().startswith("\\item") else "")
        if _balanced(joined):
            for number, sentence in enumerate(split_sentences(joined)):
                out.append((indent if number == 0 else hanging) + sentence + newline)
        else:  # ambiguous nesting: leave the block exactly as it was
            out.extend(line + newline for line in block)
        block.clear()

    for raw in lines:
        line = raw.rstrip("\r\n")
        skipping = any(env in SKIP_ENVS for env in env_stack)

        begins = BEGIN_ENV.findall(line)
        ends = END_ENV.findall(line)
        if begins or ends or not _is_prose(line) or skipping:
            flush()
            out.append(raw if raw.endswith(("\n", "\r")) else raw + newline)
            for env in begins:
                env_stack.append(env)
            for _ in ends:
                if env_stack:
                    env_stack.pop()
            continue

        # \item and \caption start a new block but keep their own text.
        if re.match(r"\s*\\(?:item\b|caption\b)", line) and block:
            flush()
        block.append(line)

    flush()
    result = "".join(out)
    if source and not source.endswith("\n"):
        result = result.rstrip("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="LaTeX files to reflow")
    parser.add_argument("--diff", action="store_true", help="print a diff only")
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if a file would change"
    )
    args = parser.parse_args(argv)

    changed = False
    for path in args.files:
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        result = reflow(source)
        if result == source:
            continue
        changed = True
        if args.diff or args.check:
            if args.diff:
                sys.stdout.writelines(
                    difflib.unified_diff(
                        source.splitlines(keepends=True),
                        result.splitlines(keepends=True),
                        fromfile=path,
                        tofile=path,
                    )
                )
            else:
                print(f"would reflow: {path}")
            continue
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(result)
        print(f"reflowed: {path}")

    return 1 if (changed and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
