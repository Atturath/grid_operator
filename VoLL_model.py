# Currently, there is only five nodes, with their properties specified

import numpy as np
import networkx as nx
from scipy.optimize import linprog

BASE_MVA = 100
KM_PER_UNIT = 10
CAP_MW = {110: 100, 220: 300}
X_PER_KM = {110: 0.0033, 220: 0.0008}
VOLL = 5000  # $/MWh value of lost load

# this is the grid  for defining the node
nodes = {"R1": (0, 15), "R2": (10, 15), "R3": (10, 10), "IND": (5, 10), "AGR": (5, 0)} 
# lines and their voltage
lines = [
    ("R1", "R2", 110, "existing"),
    ("R1", "IND", 110, "existing"),
    ("IND", "R3", 110, "existing"),
    ("IND", "AGR", 220, "existing"),
    ("R2", "R3", 110, "option"),
]
# name, node, max MW, cost $/MWh
# existing generation. Note that only Industrial and agricultural has large local generation. Small solar PV at residential nodes is ignored. 
gens = [
    ("HV_IND", "IND", 250, 30),
    ("HV_AGR", "AGR", 200, 20),
    ("LOC_IND", "IND", 50, 70),
    ("LOC_AGR", "AGR", 40, 60),
]
# stiff outside grid: node -> (limit MW, price $/MWh). R1/R2 tie attached at R1.
ties = {"R1": (80, 90), "R3": (60, 90)}


def build(options=(), cap_scale=None):
    G = nx.Graph()
    for n, p in nodes.items():
        G.add_node(n, pos=p)
    for a, b, kv, st in lines:
        if st == "option" and (a, b) not in options:
            continue
        km = np.hypot(*np.subtract(nodes[a], nodes[b])) * KM_PER_UNIT
        cap = CAP_MW[kv] * (cap_scale or {}).get((a, b), 1.0)
        G.add_edge(a, b, kv=kv, x_pu=X_PER_KM[kv] * km, cap_mw=cap)
    return G


def solve(G, load, tie_on=None, gen_out=(), tie_price=None):
    names = list(nodes)
    ni = {n: i for i, n in enumerate(names)}
    N = len(names)
    tie_on = tie_on or {n: True for n in ties}
    tie_price = tie_price or {}
    gl = [g for g in gens if g[0] not in gen_out]
    tl = [(n, *ties[n]) for n in ties if tie_on.get(n, True)]
    # variable layout: [gen..., tie..., shed(N), theta(N)]
    ng, nt = len(gl), len(tl)
    nv = ng + nt + N + N
    og, ot, os_, oth = 0, ng, ng + nt, ng + nt + N
    c = np.zeros(nv)
    bounds = [None] * nv
    for k, g in enumerate(gl):
        c[og + k] = g[3]
        bounds[og + k] = (0, g[2])
    for k, t in enumerate(tl):
        c[ot + k] = tie_price.get(t[0], t[2])
        bounds[ot + k] = (-t[1], t[1])
    for i in range(N):
        c[os_ + i] = VOLL
        bounds[os_ + i] = (0, load[names[i]])
        bounds[oth + i] = (0, 0) if names[i] == "IND" else (-np.pi, np.pi)  # slack
    # nodal balance: gen + tie + shed - sum_j y_ij (th_i - th_j)*BASE = load
    A = np.zeros((N, nv))
    for k, g in enumerate(gl):
        A[ni[g[1]], og + k] = 1
    for k, t in enumerate(tl):
        A[ni[t[0]], ot + k] = 1
    for i in range(N):
        A[i, os_ + i] = 1
    for a, b, d in G.edges(data=True):
        y = BASE_MVA / d["x_pu"]
        i, j = ni[a], ni[b]
        A[i, oth + i] -= y; A[i, oth + j] += y
        A[j, oth + j] -= y; A[j, oth + i] += y
    beq = np.array([load[n] for n in names])
    # line limits
    Aub, bub, order = [], [], []
    for a, b, d in G.edges(data=True):
        y = BASE_MVA / d["x_pu"]
        row = np.zeros(nv)
        row[oth + ni[a]] = y; row[oth + ni[b]] = -y
        Aub.append(row); bub.append(d["cap_mw"])
        Aub.append(-row); bub.append(d["cap_mw"])
        order.append((a, b, y))
    res = linprog(c, A_ub=np.array(Aub), b_ub=bub, A_eq=A, b_eq=beq,
                  bounds=bounds, method="highs")
    if res.status != 0:
        return None
    x = res.x
    prices = dict(zip(names, res.eqlin.marginals))
    flows = {(a, b): y * (x[oth + ni[a]] - x[oth + ni[b]]) for a, b, y in order}
    return dict(cost=res.fun, price=prices, flow=flows,
                shed={n: x[os_ + ni[n]] for n in names},
                gen={g[0]: x[og + k] for k, g in enumerate(gl)},
                tie={t[0]: x[ot + k] for k, t in enumerate(tl)})


def show(title, r):
    print(f"\n== {title} ==")
    if r is None:
        print("infeasible"); return
    print("cost $/h:", round(r["cost"]))
    print("prices  :", {k: round(v, 1) for k, v in r["price"].items()})
    print("flows MW:", {f"{a}->{b}": round(v, 1) for (a, b), v in r["flow"].items()})
    print("gen     :", {k: round(v, 1) for k, v in r["gen"].items()})
    print("ties    :", {k: round(v, 1) for k, v in r["tie"].items()})
    sh = {k: round(v, 1) for k, v in r["shed"].items() if v > 0.01}
    print("shed MW :", sh or "none")


if __name__ == "__main__":
    load = {"R1": 60, "R2": 50, "R3": 50, "IND": 120, "AGR": 30}
    G = build()
    show("base", solve(G, load))
    show("evening peak (residential +60%)",
         solve(G, {**load, "R1": 96, "R2": 80, "R3": 80}))
    H = build()
    H.remove_edge("R1", "IND")
    show("R1-IND trips (islands R1+R2)", solve(H, load))
    H2 = build()
    H2.remove_edge("IND", "R3")
    show("IND-R3 trips", solve(H2, load))
    show("both ties lost, peak load",
         solve(G, {**load, "R1": 96, "R2": 80, "R3": 80}, tie_on={"R1": False, "R3": False}))
    G2 = build(options={("R2", "R3")})
    show("peak load WITH R2-R3 built",
         solve(G2, {**load, "R1": 96, "R2": 80, "R3": 80}))
