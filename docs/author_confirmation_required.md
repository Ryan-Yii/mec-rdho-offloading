# Author Confirmation Required

The following items do not block a conservative, reproducible V2 build.  They
must be confirmed before journal submission.

1. **Target journal template and double-blind policy.** No journal template or
   author/anonymisation rule was supplied.  The review document format is
   preserved; final journal layout and metadata need author confirmation.
2. **Journal-specific title policy.** The current title follows the latest
   title-thread reply: "RIME-DBO-Based Capacity-Feasible Task Offloading and
   Resource Allocation in Mobile Edge Computing." Confirm only whether the
   target journal requires algorithm names to be removed from article titles.
3. **Parameter provenance.** CPU ranges, link rates, fixed service overheads,
   and QoE coefficients describe a simulation scenario, not a hardware
   calibration.  Confirm data/source citations if a field deployment claim is
   desired.
4. **Energy boundary.** The V2 default reports device-side energy only.  A
   system-wide energy conclusion would require a separate infrastructure energy
   model and rerun.
5. **AoI scope.** V2 uses a periodic, no-backlog average-AoI approximation.
   Queue-aware/peak-AoI claims require a different dynamic model and rerun.
6. **Reference bibliography.** The supplied reference PDFs help write the
   related work, but the final journal bibliography and copyright/self-overlap
   review require author approval.
7. **Requested fairness sentence conflicts with V2 evidence.** The requested
   conclusion wording says Greedy-ED slightly leads fairness, but the locked V2
   summary and Table 5 report active-user fairness 0.9244 for RDHO-full and
   0.9164 for Greedy-ED. The manuscript therefore follows the CSV and identifies
   RDHO-full as the fairness leader; no result or experiment was changed.
