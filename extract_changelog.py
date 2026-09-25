"""Extract the paper's deviations longtable + version history into CHANGELOG.md.

Panel consensus (4/4 models): the full audit ledger should live in a durable repository
artifact, with only a compact current-status box remaining in the paper. Nothing is
deleted; this moves it and converts LaTeX to markdown.
"""
import pathlib
import re

HERE = pathlib.Path(__file__).parent
tex = (HERE / "paper.tex").read_text()


def delatex(t: str) -> str:
    """LaTeX -> readable markdown. No em dashes (public-markdown rule)."""
    t = t.replace("\n", " ")
    t = re.sub(r"\\texttt\{([^{}]*)\}", r"`\1`", t)
    t = re.sub(r"\\tool\{([^{}]*)\}", r"`\1`", t)
    t = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", t)
    t = re.sub(r"\\emph\{([^{}]*)\}", r"*\1*", t)
    t = re.sub(r"\\S\\ref\{([^{}]*)\}", r"(section `\1`)", t)
    t = re.sub(r"\\ref\{([^{}]*)\}", r"(`\1`)", t)
    t = re.sub(r"\\cite[tp]?\{([^{}]*)\}", r"[\1]", t)
    # maths that carries meaning, resolved BEFORE stripping backslash commands
    t = t.replace(r"\rightarrow", " -> ").replace(r"\to", " -> ")
    t = t.replace(r"\times", " x ").replace(r"\gg", " >> ").replace(r"\ll", " << ")
    t = t.replace(r"\leq", " <= ").replace(r"\geq", " >= ").replace(r"\neq", " != ")
    t = t.replace(r"\pm", " +/- ").replace(r"\approx", " ~ ")
    t = re.sub(r"\^\{([^{}]*)\}", r"^\1", t)
    t = re.sub(r"_\{([^{}]*)\}", r"_\1", t)
    t = re.sub(r"\$([^$]*)\$", r"\1", t)
    t = t.replace(r"\%", "%").replace(r"\_", "_").replace(r"\&", "&")
    t = t.replace(r"\ldots", "...").replace(r"\eg", "e.g.")
    # no em/en dashes (public-markdown rule). Ranges between digits become "to"; a
    # double hyphen inside a word (Mann--Whitney) is a hyphen, not a range.
    t = t.replace("---", ", ")
    t = re.sub(r"(?<=\d)--(?=\d)", " to ", t)
    t = t.replace("--", "-")
    t = t.replace("``", '"').replace("''", '"')
    t = re.sub(r"\\[a-zA-Z]+", "", t)
    t = t.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", t).strip()


def rows_of(block: str) -> list[list[str]]:
    body = block[block.index(r"\endlastfoot") + len(r"\endlastfoot"):] \
        if r"\endlastfoot" in block else block
    out = []
    for raw in body.split(r"\\"):
        raw = raw.strip()
        if not raw or raw.startswith(r"\end") or raw.startswith(r"\bottomrule"):
            continue
        if r"\midrule" in raw:
            raw = raw.split(r"\midrule")[-1]
        cells = [delatex(c) for c in raw.split("&")]
        if any(cells):
            out.append(cells)
    return out


i = tex.index(r"\begin{longtable}", tex.index("Preregistration deviations across all probes") - 400)
j = tex.index(r"\end{longtable}", i) + len(r"\end{longtable}")
dev_block = tex[i:j]

k = tex.index(r"\section{Full Version History and Correction Record}")
m = len(tex)
for cand in re.finditer(r"\n\\section\{", tex[k + 10:]):
    m = k + 10 + cand.start()
    break
vh_block = tex[k:m]

parts = ["# Correction and Deviation Record",
         "",
         "Full audit ledger for **Forensic Trajectory Signatures** (arXiv:2606.30566).",
         "",
         "This file is the authoritative, complete record of every preregistration deviation,",
         "withdrawn claim, and correction across all versions of the paper. It was moved out of",
         "the paper itself because the ledger had grown to roughly 13 of 84 pages and was",
         "competing with the scientific content for the reader's attention. The paper retains a",
         "compact current-status summary and points here.",
         "",
         "Nothing has been removed in the move. Entries are append-only: an entry is never edited",
         "or deleted once written, because the value of this file is the reasoning trail.",
         "",
         "## Preregistration deviations, all probes",
         "",
         "| Probe | Deviation | Detail | Disposition |",
         "|---|---|---|---|"]

skipped = 0
for r in rows_of(dev_block):
    if len(r) == 1 and r[0]:
        parts.append(f"| | **{r[0]}** | | |")
        continue
    if len(r) < 4:
        skipped += 1
        continue
    parts.append("| " + " | ".join(c.replace("|", r"\|") for c in r[:4]) + " |")

parts += ["", "## Full version history", "",
          delatex(vh_block.replace(r"\section{Full Version History and Correction Record}", "")),
          "", "---", "",
          "Generated from `paper.tex` by `extract_changelog.py`. To regenerate after editing",
          "the paper's correction notes, re-run that script.", ""]

(HERE / "CHANGELOG.md").write_text("\n".join(parts) + "\n")
print(f"CHANGELOG.md written: {len(chr(10).join(parts))} chars, "
      f"{sum(1 for p in parts if p.startswith('| '))} table rows, {skipped} rows skipped")
