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
        # 4a. AUDIT COMPLETENESS (added 2026-09-24). The loop below iterates the
        # experiments *present* in the audit record. That made the check fail-OPEN on
        # omission: an experiment absent from the record was never tested, so its inert
        # factors passed vacuously. B+ was absent and reused the 36-configuration grid
        # with only its domain/doctype axis reaching retrievable content, so its 36
        # scenario_ids collapse to 6 distinct strings and its published trial-level
        # intervals were anti-conservative. Enumerate every clustered experiment here and
        # require it to be enrolled, so a future experiment cannot skip the audit by
        # simply not appearing in it.
        REQUIRED_AUDIT_EXPERIMENTS = {
            "x1_minja", "x1_zombie", "x4", "bplus_email", "bplus_share",
            # Enrolled 2026-09-24 in the same sweep: X5/X6 inherit minja's inert
            # `similarity` (and sample only the 2-domain prefix minja_grid()[:12]), and X2
            # clusters on scenario_id from a different grid (probe_v3_3's), which the
            # x_grid-based audit would otherwise never see. X2 turns out to have no inert
            # factor, but "checked and clean" and "never checked" must not look identical.
            "x5", "x6",
            # Enrolled 2026-09-24 (fourth pass), PER ARM. The previous sweep enrolled X2 as
            # a single experiment and recorded "all four factors consumed", which is true of
            # its control and treatment arms and FALSE of its benign keystone: that arm runs
            # probe_v3_3.run_benign_arm, whose trigger is a module constant and whose store
            # is scenario["decoy_facts"] alone, so 36 scenario_ids collapse to the 2 entries
            # of DECOY_SUBSETS. An experiment-level entry cannot express a per-arm inert set,
            # so the enrollment that was supposed to close the hole gave the affected arm a
            # clean bill of health instead. V3-1 and V3-3 were not enrolled at all, which is
            # the same fail-open-on-omission defect this assertion exists to prevent -- and
            # V3-3's benign keystone carries the paper's sharpest behavioural claim.
            "v3_1", "v3_3_attack", "v3_3_benign", "x2_attack", "x2_benign",
        }
        missing = sorted(REQUIRED_AUDIT_EXPERIMENTS - set(audit))
        if missing:
            print(f"FAIL inert_factor_audit incomplete: {missing} absent from the audit "
                  "record, so their grid factors were never checked. Every experiment "
                  "that clusters on scenario_id must be enrolled in CONSUMED_FACTORS / "
                  "GRID_FACTORS in build_manifest.py; an omitted experiment passes this "
                  "check vacuously, which is the defect this assertion closes.")
            ok = False
        extra = sorted(set(audit) - REQUIRED_AUDIT_EXPERIMENTS)
        if extra:
            print(f"WARN inert_factor_audit contains unenrolled experiments {extra}; add "
                  "them to REQUIRED_AUDIT_EXPERIMENTS so the completeness check covers them")
        # 4b. DECLARED UNIT MUST ACTUALLY COLLAPSE THE INERT FACTORS (added 2026-09-24).
        # Declaring a unit is worthless if that unit does not reproduce the reported
        # clusters. x_grid.effective_cluster_key is experiment-blind: it collapses
        # `similarity` for minja-grid ids and returns every other id unchanged, so naming
        # it for B+ would point at 12 clusters (email) or 36 (share, identity) while the
        # paper reports 6. Measured on the released records, hence a FAIL not a WARN.
        for exp, a in audit.items():
            if "declared_unit_collapses_inert" not in a:
                print(f"FAIL {exp} audit entry predates the declared-unit check; "
                      "rebuild with build_manifest.py")
                ok = False
            elif not a["declared_unit_collapses_inert"]:
                print(f"FAIL {exp} declares cluster unit "
                      f"{a.get('declared_cluster_unit')!r} but that unit does not collapse "
                      f"its inert factor(s) {a.get('inert_factors')}; the declared unit "
                      "would not reproduce the reported effective-cluster count")
                ok = False
        for exp, a in audit.items():
            if a.get("has_inert_factor"):
                declared = (a.get("declared_cluster_unit") or "")
                sev = "WARN" if declared and declared != "scenario_id" else "FAIL"
                print(f"{sev} inert factor(s) {a['inert_factors']} in {exp}: "
                      f"{a['n_scenario_ids']} scenario_ids but only "
                      f"{a['n_distinct_frozen_text']} distinct frozen-text variants "
                      f"-> cluster on {declared or '<undeclared>'}, NOT scenario_id"
                      + ("" if sev == "WARN"
                         else f" [manifest declares valid_cluster_unit={declared!r};"
                              " must declare a unit that collapses the inert factors]"))
                if sev == "FAIL":
                    ok = False
    print("PREFLIGHT", "OK" if ok else "FAILED")
    return ok


def _all_text(exp):
    """Concatenate all frozen content strings for an experiment (for contamination audit).

    Scope note: this covers exactly the experiments PROGRAM_EXECUTION_ADDENDUM.md is
    "shared, binding on" -- X1, X4, B+, X5, X6. V3-1/V3-2/V3-3/V3-6/V3-6b/X2 are governed
    by their own, earlier preregistrations that do not carry this addendum's
    experiment-unique-destination requirement, and they visibly reuse a small shared pair
    of attacker addresses (attacker@evil.example.com, auditor@external-compliance.com)
    across each other by apparent design, not by leakage -- folding them into this same
    check would flag that shared vocabulary as a false-positive contamination failure.
    """
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
    if exp == "x5":
        # X5 draws the same minja grid/mechanism as x1_minja, substituting its own
        # attacker destination (xc.ATTACKER["x5"]) via minja_poison_case's `atk` param --
        # the same substitution build_manifest.py performs for x1_minja above.
        for c in x_grid.minja_grid():
            pc = xc.minja_poison_case(c["domain"], c["framing"], xc.ATTACKER["x5"])
            parts += [pc["user"], pc["assistant"]]
    if exp == "x6":
        for c in x_grid.minja_grid():
            pc = xc.minja_poison_case(c["domain"], c["framing"], xc.ATTACKER["x6"])
            parts += [pc["user"], pc["assistant"]]
    if exp in ("bplus_email", "bplus_share"):
        # B+ is deliberately poison-free (xc.ATTACKER["bplus"] is None): its only
        # frozen content is the shared benign filler bank (included for every experiment
        # below) plus a fixed legitimate external contact defined in probe_bplus.py
        # (LEGIT_EXT). We don't import probe_bplus here to keep this preflight check
        # side-effect-free; the DOMAIN_FILLERS check below still catches the case that
        # actually matters -- an attacker destination leaking INTO benign content.
        pass
    # benign fillers are shared/benign; include to ensure no dest leaks in
    for pairs in xc.DOMAIN_FILLERS.values():
        for (u, a) in pairs:
            parts += [u, a]
    return " ".join(parts).lower()


def timeline_and_authorization_audit():
    """Addendum F/D2: 'the B+ independent memory-relevance pilot runs FIRST; its passing
    scenario_ids are frozen in MECHANISM_MANIFEST and committed. Only then do X1/X4/B+-
    confirmatory/X5/X6 collect' and 'confirmatory collection is authorized only by the
    stage-2 commit' (results/bplus/bplus_stage2_selection.json).

    No per-trial timestamp is recorded in most of these JSONL records (see the paper's
    measured git-provenance-coverage disclosure: probe_x1/probe_x4/the original probe_bplus
    collection wrote records directly and did not capture timing), so timing is inferred
    from GIT COMMIT HISTORY where available (author dates are preserved in the commit
    object and do not reset on checkout/rsync/repo-reorg the way filesystem timestamps do
    -- this is the authoritative signal), falling back to filesystem timestamps only for
    untracked files.

    Fixed 2026-09-25: an earlier revision compared every confirmatory file's start time
    against ONLY the CURRENT mtime of bplus_stage2_selection.json. That produced a false
    positive: the X1 MINJA gpt-4.1 continuation was committed 2026-09-19T11:58 under the
    ORIGINAL bplus_stage2_selection.json (first committed 2026-09-11, still valid at
    11:58), but the file was legitimately overwritten later that same day at 14:45 by an
    UNRELATED B+ re-collection (fixing B+'s own v1.3 instrumentation defect, nothing to
    do with X1). Comparing against only the current mtime made a same-day, unrelated
    overwrite look like an ordering violation. Using the file's EARLIEST git commit
    (i.e. "was SOME valid stage-2 selection in place by time T", not "does the file's
    current content date from before T") closes that gap; verified against this exact
    case (see paper.tex Reproducibility section / CHANGELOG.md for the same episode).
    """
    import subprocess
    ok = True
    REPO_ROOT = HERE.parent  # git commands need the repo root, not paper_a/

    def _git_commit_dates(abspath):
        """All commit author-dates (unix ts) touching abspath, oldest first. [] if git is
        unavailable, the path is untracked, or this is not a git repository."""
        try:
            relpath = str(abspath.relative_to(REPO_ROOT))
        except ValueError:
            return []
        try:
            out = subprocess.run(
                ["git", "log", "--follow", "--format=%at", "--", relpath],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=15)
            if out.returncode != 0 or not out.stdout.strip():
                return []
            return sorted(int(l) for l in out.stdout.splitlines() if l.strip())
        except Exception:
            return []

    selection = HERE / "results" / "bplus" / "bplus_stage2_selection.json"
    stage2_dates = _git_commit_dates(selection)
    if stage2_dates:
        # Earliest commit, not latest: a valid stage-2 selection has existed since then,
        # even if a later, unrelated re-collection has since overwritten the file's
        # current content (see docstring above).
        stage2_time, stage2_source = stage2_dates[0], "git:earliest-commit"
    elif selection.exists():
        stage2_time, stage2_source = selection.stat().st_mtime, "filesystem:mtime(untracked)"
    else:
        stage2_time, stage2_source = None, "MISSING"
        print("TIMELINE-AUDIT SKIP: no bplus_stage2_selection.json yet "
              "(stage-2 not authorized; confirmatory collection must not have started)")

    def _start_time(p):
        dates = _git_commit_dates(p)
        if dates:
            return dates[0], "git:earliest-commit"
        st = p.stat()
        return getattr(st, "st_birthtime", st.st_mtime), "filesystem:birthtime"

    confirmatory_globs = {
        "bplus_email": (HERE / "results" / "bplus").glob("bplus_email_*.jsonl"),
        "bplus_share": (HERE / "results" / "bplus").glob("bplus_share_*.jsonl"),
        "x1": (HERE / "results" / "x1").glob("x1_*.jsonl"),
        "x4": (HERE / "results" / "x4").glob("x4_*.jsonl"),
        "x5": (HERE / "results" / "x5").glob("x5_*.jsonl"),
        "x6": (HERE / "results" / "x6").glob("x6_*.jsonl"),
    }
    violations = []
    fs_fallback_used = []
    for label, files in confirmatory_globs.items():
        for p in files:
            start, source = _start_time(p)
            if source.startswith("filesystem"):
                fs_fallback_used.append(str(p.relative_to(HERE)))
            if stage2_time is None or start < stage2_time:
                violations.append((label, str(p.relative_to(HERE)), start, stage2_time, source))
    # Filesystem-event guard (only relevant to the filesystem-timestamp fallback path,
    # i.e. files git has no history for): st_birthtime resets on copy/checkout, not just
    # on original write. If many untracked files across DIFFERENT experiments share the
    # exact same start second, that is the signature of a bulk filesystem event, not
    # genuine per-session collection order -- WARN rather than FAIL for those.
    from collections import Counter
    fs_violations = [v for v in violations if v[4].startswith("filesystem")]
    git_violations = [v for v in violations if v[4].startswith("git")]
    ts_counts = Counter(round(v[2]) for v in fs_violations)
    bulk_timestamps = {ts for ts, n in ts_counts.items() if n >= 3}
    real_fs_violations = [v for v in fs_violations if round(v[2]) not in bulk_timestamps]
    bulk_violations = [v for v in fs_violations if round(v[2]) in bulk_timestamps]
    real_violations = git_violations + real_fs_violations
    if bulk_violations:
        shared = sorted(bulk_timestamps)
        print(f"WARN timeline audit: {len(bulk_violations)} untracked file(s) share "
              f"{len(shared)} exact start-timestamp(s) across multiple experiments -- "
              "almost certainly a bulk filesystem event (repo reorg/checkout/rsync resets "
              "st_birthtime on copy), not genuine per-session collection order. Treated as "
              f"untrustworthy-for-ordering, not a violation. Shared timestamps: {shared}")
    if real_violations:
        print("FAIL timeline/authorization audit: confirmatory file(s) whose earliest "
              "known timestamp (git commit where tracked, filesystem birthtime otherwise) "
              "predates the earliest valid stage-2 selection commit (Addendum F/D2 "
              "requires pilot -> freeze -> confirmatory in that order):")
        for label, relpath, start, stage2, source in real_violations:
            stage2_str = f"{stage2:.0f}" if stage2 is not None else "MISSING"
            print(f"  [{label}] {relpath} ({source}): started {start:.0f}, "
                  f"stage-2 earliest authorization {stage2_str} ({stage2_source})")
        ok = False
    elif stage2_time is not None:
        print(f"TIMELINE-AUDIT OK: stage-2 first authorized at {stage2_time:.0f} "
              f"({stage2_source}); no confirmatory file predates that")
    return ok



def contamination_audit():
    """Each experiment's dest must appear ONLY in its own content (Addendum F/D2 scope:
    X1, X4, B+, X5, X6 -- see the scope note in _all_text() for why V3-1/V3-2/V3-3/V3-6/
    V3-6b/X2 are not enrolled here)."""
    ok = True
    exps = {"x1_minja": xc.ATTACKER["x1_minja"], "x1_zombie": xc.ATTACKER["x1_zombie"],
            "x4": xc.ATTACKER["x4"], "x5": xc.ATTACKER["x5"], "x6": xc.ATTACKER["x6"]}
    texts = {e: _all_text(e) for e in exps}
    # B+ is poison-free by design (no attacker destination of its own); its check is
    # one-directional -- do any OTHER experiment's destinations leak into B+'s content?
    for bp_exp in ("bplus_email", "bplus_share"):
        texts[bp_exp] = _all_text(bp_exp)
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
    c = timeline_and_authorization_audit()
    sys.exit(0 if (a and b and c) else 1)
