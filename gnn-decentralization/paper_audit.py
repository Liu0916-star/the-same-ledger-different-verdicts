# -*- coding: utf-8 -*-
"""paper_audit.py -- consistency check between manuscript and results.

1. every \\V{key} in the text is defined in numbers.tex (fails otherwise)
2. no \\tbd{...} is left in the text (fails otherwise)
3. lists numbers typed by hand (not through \\V), so that a person can confirm
   they are constants (dates, thresholds, parameters) rather than results.
   Whitelist: ALLOWED.
Usage: python paper_audit.py   (non-zero exit code = failed)
"""
import re
import sys

import config as C

PAPER = C.ROOT.parent / "paper"
SECTIONS = sorted((PAPER / "sections").glob("*.tex"))
# constants that may be typed by hand: window and snapshot dates, guideline
# thresholds, rule parameters, model hyperparameters, numbers quoted from the literature
ALLOWED = {
    "2026", "2025", "2023", "2010", "1982", "2017", "2019", "2020", "2021", "2022", "2024",
    "90", "48", "0.01", "1{,}000", "1{,}500", "1{,}800", "2{,}500", "10^{4}", "10^4",
    "5\\times10^{4}", "5\\times10^4", "10^{8}", "4\\times10^{7}", "10^{9}", "-10^{9}",
    "500", "5{,}000", "16", "32", "200", "0.01", "10", "5", "1", "0", "2", "3", "4",
    "13", "7", "29{,}945", "29{,}772", "173", "20", "100", "50", "8", "12",
}


def strip(tex: str) -> str:
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    for pat in (r"\\V\{[^}]*\}", r"\\(cite|ref|label|eqref|url|href|includegraphics|input)\{[^}]*\}",
                r"\\texttt\{[^}]*\}", r"\\begin\{equation\}.*?\\end\{equation\}"):
        tex = re.sub(pat, " ", tex, flags=re.S)
    return tex


def main():
    nums = (PAPER / "numbers.tex").read_text(encoding="utf-8")
    defined = set(re.findall(r"\\csname v@([^\\]+)\\endcsname", nums))
    bad, tbd, literal = [], [], []
    for f in SECTIONS:
        tex = f.read_text(encoding="utf-8")
        for k in re.findall(r"\\V\{([^}]*)\}", tex):
            if k not in defined:
                bad.append((f.name, k))
        tbd += [(f.name, m) for m in re.findall(r"\\tbd\{([^}]*)\}", tex)]
        for m in re.finditer(r"(?<![\w.{])(\d[\d{},.]*\d|\d)(?![\w])", strip(tex)):
            v = m.group(1).rstrip(".,")
            if v not in ALLOWED:
                literal.append((f.name, v))
    print(f"\\V keys: {len(defined)} defined")
    print(f"[{'X' if bad else 'OK'}] undefined \\V keys {len(bad)}")
    for f, k in bad:
        print(f"      {f}: {k}")
    print(f"[{'X' if tbd else 'OK'}] leftover \\tbd {len(tbd)}")
    for f, k in tbd:
        print(f"      {f}: {k[:80]}")
    print(f"[i] numbers typed by hand (confirm they are constants) {len(literal)}")
    for f, v in sorted(set(literal)):
        print(f"      {f}: {v}")
    sys.exit(1 if (bad or tbd) else 0)


if __name__ == "__main__":
    main()
