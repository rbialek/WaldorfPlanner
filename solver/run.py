"""Main entry point for the timetable solver."""

import sys
import time
from pathlib import Path

from .parser import parse_all
from .model import build_model
from .generator import generate_all


def main(data_dir: str = None, output_dir: str = None, timeout: int = 120):
    project_root = Path(__file__).parent.parent
    if data_dir is None:
        data_dir = project_root / "dane" / "2026-27"
    if output_dir is None:
        output_dir = project_root / "plany"

    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

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
    print(f"\nUruchamianie solvera (timeout: {timeout}s)...")
    start = time.time()
    solution = build_model(data, timeout_seconds=timeout)
    elapsed = time.time() - start

    if solution is None:
        print(f"\nBLAD: Solver nie znalazl rozwiazania (INFEASIBLE lub timeout po {elapsed:.1f}s)")
        print("Sprawdz dane wejsciowe - moze byc za duzo ograniczen.")
        sys.exit(2)

    print(f"  Status: {solution['status']} (w {elapsed:.1f}s)")
    print(f"  Funkcja celu: {solution.get('objective', 'N/A')}")

    # Generate
    print(f"\nGenerowanie planow do {output_dir}...")
    generate_all(data, solution, output_dir)

    # List generated files
    generated = sorted(output_dir.glob("*.md"))
    print(f"  Wygenerowano {len(generated)} plikow:")
    for f in generated:
        print(f"    {f.name}")

    print("\nGotowe!")


if __name__ == "__main__":
    timeout = 120
    if len(sys.argv) > 1:
        try:
            timeout = int(sys.argv[1])
        except ValueError:
            pass
    main(timeout=timeout)
