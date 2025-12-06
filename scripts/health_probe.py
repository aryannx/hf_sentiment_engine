#!/usr/bin/env python3
import argparse
import subprocess
import time


def run_probe(cmd):
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    latency = time.time() - start
    return proc.returncode, latency, proc.stdout.strip(), proc.stderr.strip()


def main():
    parser = argparse.ArgumentParser(description="Uptime/latency probe for CLI healthchecks")
    parser.add_argument("--cmd", nargs="+", default=["python", "-m", "src.main", "--healthcheck"])
    args = parser.parse_args()

    code, latency, out, err = run_probe(args.cmd)
    status = "OK" if code == 0 else "FAIL"
    print(f"status={status} code={code} latency={latency:.3f}s")
    if out:
        print(f"stdout: {out}")
    if err:
        print(f"stderr: {err}")


if __name__ == "__main__":
    main()

