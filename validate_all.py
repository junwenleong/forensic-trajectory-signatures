"""
validate_all.py — stage pre-flight + cross-experiment contamination audit (Addendum F).
Fails closed (exit 1) on any mismatch. Run before confirmatory collection and again
(with --post) after all runs to audit cross-experiment contamination in the raw trials.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x_grid
import x_content as xc

MANIFEST = HERE / "MECHANISM_MANIFEST.json"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def preflight():
    ok = True
    m = json.loads(MANIFEST.read_text())
    # 1. code hashes match
    for fn, h in m["code_hashes"].items():
        cur = _sha(HERE / fn)
        if cur != h:
            print(f"FAIL hash mismatch {fn}: manifest {h[:12]} != current {cur[:12]}"); ok = False
    # 2. grids 36-unique
    for name, fn in x_grid.GRIDS.items():
        g = fn(); ids = [c["scenario_id"] for c in g]
        if len(g) != 36 or len(set(ids)) != 36:
            print(f"FAIL grid {name}: {len(g)} configs / {len(set(ids))} unique"); ok = False
    # 3. per-experiment attacker destinations distinct
    dests = [v for v in xc.ATTACKER.values() if v]
    if len(dests) != len(set(dests)):
        print(f"FAIL attacker destinations not distinct: {dests}"); ok = False
    # 4. no inert grid factors (added 2026-09-19; made fail-closed 2026-09-19)
    # A factor that never reaches the content constructor does not create a distinct
    # scenario; it silently multiplies the scenario_id count and inflates the
    # >=10-success-contributing-cluster confirmatory gate. This is the exact defect that
    # forced the MINJA A->P retraction, so it is FAIL, not WARN: preflight must not pass
    # while an undeclared inert factor is present. A detected inert factor is acceptable
    # only once the manifest declares the effective clustering unit for that experiment.
    audit = m.get("inert_factor_audit")
    if audit is None:
        print("FAIL inert_factor_audit missing from manifest; rebuild with build_manifest.py")
        ok = False
    else:
        for exp, a in audit.items():
            if a.get("has_inert_factor"):
                declared = (a.get("valid_cluster_unit") or "")
                sev = "WARN" if declared.startswith("effective_cluster_key") else "FAIL"
                print(f"{sev} inert factor(s) {a['inert_factors']} in {exp}: "
                      f"{a['n_scenario_ids']} scenario_ids but only "
                      f"{a['n_distinct_frozen_text']} distinct frozen-text variants "
                      f"-> cluster on x_grid.effective_cluster_key, NOT scenario_id"
                      + ("" if sev == "WARN"
                         else f" [manifest declares valid_cluster_unit={declared!r};"
                              " must declare effective_cluster_key]"))
                if sev == "FAIL":
                    ok = False
    print("PREFLIGHT", "OK" if ok else "FAILED")
    return ok


def _all_text(exp):
    """Concatenate all frozen content strings for an experiment (for contamination audit)."""
    parts = []
    if exp in ("x1_minja",):
        for c in x_grid.minja_grid():
            pc = xc.minja_poison_case(c["domain"], c["framing"], xc.ATTACKER["x1_minja"])
            parts += [pc["user"], pc["assistant"]]
    if exp in ("x1_zombie",):
        for c in x_grid.zombie_grid():
            parts.append(xc.zombie_routing(c["domain"], c["keyspan"], xc.ATTACKER["x1_zombie"]))
    if exp == "x4":
        for c in x_grid.x4_grid():
            form = xc.x4_recipient_form(c["recipient_rep"], xc.ATTACKER["x4"])
            parts.append(xc.x4_routing_rule(c["doctype"], form))
    # benign fillers are shared/benign; include to ensure no dest leaks in
    for pairs in xc.DOMAIN_FILLERS.values():
        for (u, a) in pairs:
            parts += [u, a]
    return " ".join(parts).lower()


def contamination_audit():
    """Each experiment's attacker dest must appear ONLY in its own content."""
    ok = True
    exps = {"x1_minja": xc.ATTACKER["x1_minja"], "x1_zombie": xc.ATTACKER["x1_zombie"],
            "x4": xc.ATTACKER["x4"]}
    texts = {e: _all_text(e) for e in exps}
    for e, dest in exps.items():
        for other, txt in texts.items():
            if other == e:
                continue
            if dest.lower() in txt:
                print(f"FAIL contamination: {e} dest appears in {other} content"); ok = False
    print("CONTAMINATION-AUDIT", "OK" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    a = preflight()
    b = contamination_audit()
    sys.exit(0 if (a and b) else 1)
