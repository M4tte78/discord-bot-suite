"""CLI: `python -m botsuite.sim [raid|moderation|chat|tournament|all|list] [--json]`."""

from __future__ import annotations

import argparse
import json
import sys

from . import console
from .scenarios import SCENARIOS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m botsuite.sim",
        description="Simulateur hors-ligne des bots Discord (aucun jeton ni réseau requis).",
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default="all",
        choices=[*SCENARIOS.keys(), "all", "list"],
        help="scénario à exécuter (défaut : all)",
    )
    parser.add_argument("--json", action="store_true", help="n'afficher que le résumé JSON")
    args = parser.parse_args(argv)

    if args.scenario == "list":
        print("Scénarios disponibles :\n")
        for name, (_, description) in SCENARIOS.items():
            print(f"  {console.paint(name.ljust(12), 'bold')} {description}")
        return 0

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    summaries = []
    for name in names:
        runner, _ = SCENARIOS[name]
        summaries.append(runner(verbose=not args.json))

    if args.json:
        json.dump(summaries, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        console.title("Résumé")
        for summary in summaries:
            console.info(json.dumps(summary, ensure_ascii=False))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
