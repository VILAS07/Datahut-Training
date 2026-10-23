"""Run crawler + parser for each year, one after the other.

    python run_all.py 1921 2026        # years 1921 to 2026
    python run_all.py 1990             # a single year

Change GAP_SECONDS below to set the pause between years.

Stop with Ctrl+C. Run the same command again and it carries on:
the crawler skips links it already has, the parser skips products
already saved in the CSV, so nothing is duplicated.
"""

import subprocess
import sys
import time

GAP_SECONDS = 30   # pause after each year before the next one starts


def run(*args):
    return subprocess.call([sys.executable, *args])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    first = int(sys.argv[1])
    last = int(sys.argv[2]) if len(sys.argv) > 2 else first

    for year in range(first, last + 1):
        print(f"\n########## YEAR {year} ##########", flush=True)
        if run("crawler.py", str(year)) != 0:
            print(f"crawler failed for {year}, skipping to next year", flush=True)
            continue
        # parses every link not yet in the csv (so earlier failures are retried too)
        code = run("parser.py")
        if code == 2:
            print("\nBLOCKED by the site (429). Progress is saved. "
                  "Wait 1-2 hours, then run the same command again.", flush=True)
            sys.exit(2)
        if year < last:
            print(f"year {year} finished, waiting {GAP_SECONDS}s before {year + 1}...", flush=True)
            time.sleep(GAP_SECONDS)
    print("\nALL DONE", flush=True)