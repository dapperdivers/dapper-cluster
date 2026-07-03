#!/usr/bin/env python3
"""Explore a Node-RED flows.json without hand-parsing it.

Usage:
  flowdump.py FLOWS.json                 # list tabs with node counts
  flowdump.py FLOWS.json --tab NAME      # nodes on a tab (type, name, disabled, id)
  flowdump.py FLOWS.json --grep WORD     # nodes whose JSON mentions WORD (case-insensitive)
  flowdump.py FLOWS.json --node ID       # full node JSON + incoming/outgoing wires by name
  flowdump.py FLOWS.json --wiring TAB    # adjacency list for a whole tab
"""
import argparse
import json
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def label(nodes, nid):
    n = nodes.get(nid, {})
    d = " DISABLED" if n.get("d") else ""
    return f"{n.get('name') or n.get('type', '?')} [{n.get('type')}]{d} ({nid})"


def tab_of(flows):
    return {n["id"]: n.get("label", "?") for n in flows if n["type"] == "tab"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flows")
    ap.add_argument("--tab")
    ap.add_argument("--grep")
    ap.add_argument("--node")
    ap.add_argument("--wiring")
    args = ap.parse_args()

    flows = load(args.flows)
    nodes = {n["id"]: n for n in flows}
    tabs = tab_of(flows)

    if args.node:
        n = nodes.get(args.node)
        if not n:
            sys.exit(f"no node {args.node}")
        print(json.dumps(n, indent=2))
        print("\n-- outgoing --")
        for i, w in enumerate(n.get("wires", [])):
            for t in w:
                print(f"  out{i} -> {label(nodes, t)}")
        print("-- incoming --")
        for m in flows:
            for i, w in enumerate(m.get("wires", [])):
                if args.node in w:
                    print(f"  {label(nodes, m['id'])} out{i} ->")
        return

    if args.grep:
        needle = args.grep.lower()
        for n in flows:
            if n["type"] in ("tab", "group"):
                continue
            if needle in json.dumps(n).lower():
                print(f"{tabs.get(n.get('z'), n.get('z', 'config')):20s} {label(nodes, n['id'])}")
        return

    tab_arg = args.tab or args.wiring
    if tab_arg:
        tid = next((i for i, l in tabs.items() if l.lower() == tab_arg.lower()), tab_arg)
        members = [n for n in flows if n.get("z") == tid]
        if not members:
            sys.exit(f"no tab named/id {tab_arg}; tabs: {list(tabs.values())}")
        for n in members:
            if args.wiring:
                if n["type"] in ("group", "comment"):
                    continue
                outs = [[label(nodes, t) for t in w] for w in n.get("wires", [])]
                print(f"{label(nodes, n['id'])}")
                for i, w in enumerate(outs):
                    for t in w:
                        print(f"    out{i} -> {t}")
            else:
                d = "DISABLED" if n.get("d") else ""
                print(f"{n['type']:26s} {n.get('name', ''):45s} {d:8s} {n['id']}")
        return

    for tid, lab in tabs.items():
        count = sum(1 for n in flows if n.get("z") == tid)
        disabled = sum(1 for n in flows if n.get("z") == tid and n.get("d"))
        print(f"{tid}  {lab:25s} {count} nodes ({disabled} disabled)")
    configs = sum(1 for n in flows if "z" not in n and n["type"] not in ("tab",))
    print(f"(+ {configs} global config nodes)")


if __name__ == "__main__":
    main()
