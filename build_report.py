"""Build the report from a clean checkout.

    python build_report.py            # data, figures, PDF
    python build_report.py --figures  # stop after the figures
    python build_report.py --pdf      # skip regeneration, just typeset
    python build_report.py --clean    # remove build products

The default path regenerates everything the report stands on, in order:

    results/*.csv   <- report_data.py, from the sweep and the saved matrices
    figures/*.pdf   <- figures.py, from those CSVs
    report/report.pdf

Regenerating the figures is meant to be a check rather than a chore: if a
number in the report has drifted from the data, running this is what catches
it. `report_data.py` is the slow step, because it re-derives fifteen
leave-one-out maps from the saved matrices rather than trusting a stored value.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REPORT = ROOT / "report"
FIGURES = ROOT / "figures"
DOCUMENT = "report"

# In preference order. latexmk handles the rerun-for-references dance itself;
# tectonic downloads what it needs; the plain engines need driving by hand.
ENGINES = ("latexmk", "tectonic", "pdflatex")

BUILD_SUFFIXES = (
    ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".fls", ".fdb_latexmk",
    ".synctex.gz",
)


def run(command: list[str], cwd: Path) -> int:
    print(f"  $ {' '.join(command)}")
    return subprocess.call(command, cwd=cwd)


def run_stage(script: str) -> None:
    print(f"\n=== {script} ===")
    # -u so the stage's progress appears live even when the build's own
    # output is redirected to a file; report_data.py runs for tens of
    # minutes and a silent pipe looks like a hang.
    code = subprocess.call([sys.executable, "-u", str(ROOT / script)], cwd=ROOT)
    if code != 0:
        raise SystemExit(f"{script} failed with exit code {code}")


# A fresh TeX install does not update the PATH of an already-open shell, so a
# first build right after installing would report "no engine" from a machine
# that has one. These are the default install locations worth looking in before
# giving up.
FALLBACK_BIN_DIRS = (
    Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64",
    Path("C:/Program Files/MiKTeX/miktex/bin/x64"),
    Path("/Library/TeX/texbin"),
    Path("/usr/local/texlive/bin"),
)


def find_engine() -> str | None:
    for engine in ENGINES:
        found = shutil.which(engine)
        if found:
            return found
    for directory in FALLBACK_BIN_DIRS:
        if not directory.is_dir():
            continue
        for engine in ENGINES:
            for candidate in (directory / engine, directory / f"{engine}.exe"):
                if candidate.exists():
                    # Put the whole directory on PATH: latexmk shells out to
                    # pdflatex and bibtex, which must be findable too.
                    os.environ["PATH"] = (
                        f"{directory}{os.pathsep}{os.environ['PATH']}"
                    )
                    print(f"  found {engine} in {directory} (added to PATH)")
                    return engine
    return None


def typeset() -> None:
    print("\n=== typesetting ===")
    engine = find_engine()
    if engine is None:
        print(
            "  No TeX engine found. The skeleton and figures are complete and\n"
            "  the PDF stage is the only thing missing; install one of:\n"
            "\n"
            "    Windows   winget install MiKTeX.MiKTeX\n"
            "    macOS     brew install --cask mactex-no-gui\n"
            "    Debian    sudo apt install texlive-latex-recommended "
            "texlive-latex-extra texlive-bibtex-extra\n"
            "    anywhere  cargo install tectonic\n"
            "\n"
            "  then re-run: python build_report.py --pdf"
        )
        raise SystemExit(2)

    engine = Path(engine).stem
    print(f"  using {engine}")
    if engine == "latexmk":
        code = run(["latexmk", "-pdf", "-interaction=nonstopmode",
                    f"{DOCUMENT}.tex"], REPORT)
    elif engine == "tectonic":
        code = run(["tectonic", f"{DOCUMENT}.tex"], REPORT)
    else:
        # pdflatex, bibtex, pdflatex, pdflatex - the classic four passes.
        code = run(["pdflatex", "-interaction=nonstopmode", f"{DOCUMENT}.tex"], REPORT)
        if code == 0 and shutil.which("bibtex"):
            run(["bibtex", DOCUMENT], REPORT)
            code = run(["pdflatex", "-interaction=nonstopmode",
                        f"{DOCUMENT}.tex"], REPORT)
            code = run(["pdflatex", "-interaction=nonstopmode",
                        f"{DOCUMENT}.tex"], REPORT)
        elif code == 0:
            print("  bibtex not found; citations will render as [?]")

    pdf = REPORT / f"{DOCUMENT}.pdf"
    if code != 0 or not pdf.exists():
        raise SystemExit(
            f"  typesetting failed (exit {code}). See report/{DOCUMENT}.log."
        )
    print(f"\n  built {pdf.relative_to(ROOT)} "
          f"({pdf.stat().st_size / 1024:.0f} KB)")


def clean() -> None:
    removed = 0
    for suffix in BUILD_SUFFIXES:
        for path in REPORT.glob(f"*{suffix}"):
            path.unlink()
            removed += 1
    pdf = REPORT / f"{DOCUMENT}.pdf"
    if pdf.exists():
        pdf.unlink()
        removed += 1
    print(f"removed {removed} build products")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--figures", action="store_true",
                        help="regenerate data and figures, then stop")
    parser.add_argument("--pdf", action="store_true",
                        help="typeset only, without regenerating anything")
    parser.add_argument("--clean", action="store_true",
                        help="remove build products and exit")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    if not args.pdf:
        run_stage("report_data.py")
        run_stage("figures.py")
        missing = [
            name for name in (
                "fig1_map_pool", "fig2_edge_profile", "fig3_roster_comparison",
                "fig4_influence", "fig5_sensitivity", "fig6_phase_b_trajectory",
            )
            if not (FIGURES / f"{name}.pdf").exists()
        ]
        if missing:
            raise SystemExit(f"figures missing after build: {missing}")
        print(f"\n  {len(list(FIGURES.glob('*.pdf')))} figures in "
              f"{FIGURES.relative_to(ROOT)}/")

    if args.figures:
        return

    typeset()


if __name__ == "__main__":
    main()
