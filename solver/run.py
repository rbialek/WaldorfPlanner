"""Main entry point for the timetable solver."""

import argparse
import sys
import time
from pathlib import Path

from .parser import parse_all
from .generator import generate_all
from .constraints import evaluate_schedule


def main():
    parser = argparse.ArgumentParser(description="School timetable solver")
    parser.add_argument(
        "--solver", choices=["cpsat", "ga"], default="ga",
        help="Solver to use: cpsat (OR-Tools CP-SAT) or ga (Genetic Algorithm, default)",
    )
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (cpsat)")
    parser.add_argument("--generations", type=int, default=200, help="GA generations")
    parser.add_argument("--population", type=int, default=100, help="GA population size")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for GA")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else project_root / "dane" / "2026-27"
    output_dir = Path(args.output_dir) if args.output_dir else project_root / "plany"

    # Verify input files exist
    required_files = ["klasy.md", "nauczyciele.md", "przedmioty.md", "matryca.md", "zasady.md"]
    missing = [f for f in required_files if not (data_dir / f).exists()]
    if missing:
        print(f"BLAD: Brakujace pliki w {data_dir}: {', '.join(missing)}")
        sys.exit(1)

    # Parse
    print(f"Wczytywanie danych z {data_dir}...")
    data = parse_all(data_dir)
    print(f"  Klasy: {len(data.classes)} ({', '.join(c.id for c in data.classes)})")
    print(f"  Uczniowie: {sum(len(c.students) for c in data.classes)}")
    print(f"  Nauczyciele: {len(data.teachers)}")
    print(f"  Przedmioty: {len(data.subjects)}")
    print(f"  Wpisy matrycy: {len(data.matrix)}")
    print(f"  Grupy jezykowe: {len(data.language_groups)}")
    print(f"  Reguly optymalizacji: {len(data.rules.optimization)}")
    for r in data.rules.optimization:
        print(f"    {r.id}: waga {r.weight}")

    # Solve
    start = time.time()

    if args.solver == "cpsat":
        from .model import build_model
        print(f"\nUruchamianie CP-SAT (timeout: {args.timeout}s)...")
        solution = build_model(data, timeout_seconds=args.timeout)
    else:
        from .ga_solver import build_ga_model, GAConfig
        config = GAConfig(
            population_size=args.population,
            generations=args.generations,
            seed=args.seed,
        )
        print(f"\nUruchamianie GA (populacja: {config.population_size}, generacje: {config.generations})...")
        solution = build_ga_model(data, config)

    elapsed = time.time() - start

    if solution is None:
        print(f"\nBLAD: Solver nie znalazl rozwiazania po {elapsed:.1f}s")
        sys.exit(2)

    print(f"\n  Status: {solution['status']} (w {elapsed:.1f}s)")
    print(f"  Fitness: {solution.get('objective', 'N/A')}")

    # Evaluate with constraint functions
    eval_result = evaluate_schedule(solution["schedule"], data)
    print(f"\n  Ewaluacja planu:")
    print(f"    Hard constraints: {eval_result['hard_total']:.0f} (500 = all pass)")
    print(f"    Soft score: {eval_result['soft_total']:.1f} / 240.0")
    print(f"    Total: {eval_result['total']:.1f}")
    print(f"    Szczegoly:")
    for name, ctype, score in eval_result["details"]:
        marker = "OK" if (ctype == "HARD" and score > 0) else ("!!" if score < 0 else "")
        print(f"      {ctype:4s} {name:30s} {score:8.1f} {marker}")

    # Generate
    print(f"\nGenerowanie planow do {output_dir}...")
    generate_all(data, solution, output_dir)

    generated = sorted(output_dir.glob("*.md"))
    print(f"  Wygenerowano {len(generated)} plikow:")
    for f in generated:
        print(f"    {f.name}")

    print("\nGotowe!")


if __name__ == "__main__":
    main()
