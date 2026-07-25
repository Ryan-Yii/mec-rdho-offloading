# Physical Offloading Model V2

## Scope

This study evaluates a simulated cloud-edge-device MEC system.  It optimises
task execution-node assignment and CPU-frequency allocation.  It does **not**
optimise bandwidth, transmit power, channel assignment, user association,
queue scheduling, or cloud routing.  All reported energy values are
device-side energy values.

Let \(\mathcal D\), \(\mathcal E\), \(\mathcal C\), and \(\mathcal T\)
denote devices, edge servers, cloud servers, and tasks.  Task \(i\) has a
source device \(d(i)\), input bits \(b_i\), CPU cycles \(c_i\), period
\(\Delta_i\), and QoS thresholds \(\bar T_i\), \(\bar E_i\), and
\(\bar A_i\).  The unified execution-node set is
\(\mathcal N=\mathcal D\cup\mathcal E\cup\mathcal C\).

For each task, the binary assignment variable \(x_{i,j}\) is one only for its
selected execution node \(j\).  The derived layer variable \(z_i\) is local,
edge, or cloud according to the type of \(j\); \(s_i\) is the selected edge or
cloud server when \(z_i\ne\text{local}\).  A physical CPU allocation
\(f_i\) is expressed in Hz.  The search variable \(r_i\in[0,1]\) is only a
normalised encoding and is never interpreted as a system-level resource.

## Legal nodes and paths

Local execution is legal only at \(d(i)\).  An edge server is legal only when
the generated device-edge rate is positive.  A cloud server is legal only when
at least one reachable edge has a positive edge-cloud rate.  For a selected
cloud, the evaluator deterministically uses the reachable relay edge with the
smallest task-specific transmission delay.  This is fixed-path evaluation,
not route or communication-resource optimisation.

## CPU decoding and repair

The continuous encoder has one node-selection coordinate and one resource
coordinate per task.  The decoder maps the former to the sorted legal-node
list and maps the latter to a tentative frequency between the selected node's
minimum allocatable frequency and capacity.  It then applies the same
deterministic repair to every algorithm:

1. If a node has more minimum-frequency assignments than it can serve, examine
   tasks in descending ID order and move each selected task to its legal
   alternative with the largest remaining minimum-frequency slack; ties use the
   smallest global node ID. Task types are shuffled before IDs are assigned,
   while source device and priority are sampled independently. A pooled audit of
   all 1,200 tasks in the 30 configured scenarios found no detectable ID
   association with type, source device, or priority. The order is therefore a
   deterministic reproducibility convention, not a task-importance rule.
2. For every node, retain each decoded request whenever its total is within
   capacity; only if the sum of requested excess frequencies exceeds the
   remaining capacity is that excess projected proportionally.

Let \(\mathcal T_j=\{i:x_{i,j}=1\}\), \(n_j=|\mathcal T_j|\), and
\(R_j=F_j-n_j f_j^{\min}\). Reassignment is attempted for at most
\(|\mathcal T||\mathcal N|\) passes and either produces non-negative \(R_j\)
for every node or fails explicitly. Projection is applied only to tasks in
\(\mathcal T_j\). If the total requested excess is no larger than \(R_j\), the
original requests are retained. A zero excess denominator therefore uses the
retention branch and is never divided by. Otherwise, requested excess above
\(f_j^{\min}\) is scaled proportionally to \(R_j\).

The generated parameter ranges ensure a feasible minimum-frequency allocation
exists. The deterministic repair keeps one legal node per task and enforces the
selected-node bound
\(\sum_jx_{i,j}f_j^{\min}\le f_i\le\sum_jx_{i,j}F_j\) and node capacity
\(\sum_i x_{i,j}f_i\le F_j\).

## Performance model

For local, edge, and cloud execution, respectively,

\[
T_i= c_i/f_i,
\]
\[
T_i= b_i/R_{d(i),s_i}+c_i/f_i+\tau_E,
\]
\[
T_i= b_i/R_{d(i),e^*(i,s_i)}+b_i/R_{e^*(i,s_i),s_i}+c_i/f_i+\tau_C.
\]

The device-side energy is \(\kappa_{d(i)}c_if_i^2\) locally and
\(P_{d(i)}b_i/R_{d(i),e}\) for either offloading path.  Edge/cloud computation
energy and backhaul energy are outside this device-side scope.  With periodic
generation and no explicit queue backlog, average AoI is approximated as
\(A_i=\Delta_i/2+T_i\).

The base per-task utility is
\[
u_i=0.45e^{-T_i/\bar T_i}+0.30e^{-E_i/\bar E_i}+0.25e^{-A_i/\bar A_i},
\]
which lies in \([0,1]\).  Priority is used only to aggregate system QoE,
\(Q=\sum_i\pi_i u_i/\sum_i\pi_i\).  Jain fairness is computed over the
mean base utility of each active source device, not over individual tasks.

The base term \(B(X)\) combines threshold-normalised energy, delay, and AoI with
\(1-Q\) and \(1-J\). The one formal problem is
\(\min_X F_{\mathrm{report}}(X)=B(X)+\lambda_{\mathrm{ref}}[1-\mathrm{CSR}(X)]\),
with \(\lambda_{\mathrm{ref}}=1\), subject to assignment validity, uniqueness,
selected-node CPU bounds, and capacity. Delay, energy, and AoI threshold
failures form the soft CSR term. \(F_{\mathrm{search}}(X,t)\) is only a dynamic
penalty-continuation mechanism for solving this fixed P1: parents and candidates
are compared at the same iteration coefficient, while all tables and statistics
use \(F_{\mathrm{report}}\).
