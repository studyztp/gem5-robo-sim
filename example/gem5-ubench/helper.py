from multiprocessing import Pool
from pathlib import Path
import subprocess
import argparse
import os

parser = argparse.ArgumentParser(
    description="Run all microbenchmarks in gem5 with entobench"
)
parser.add_argument(
    "--gem5-path", type=str, required=True, help="Path to the gem5 executable"
)
parser.add_argument(
    "--gem5-script", type=str, required=True, help="Path to the gem5 script"
)
parser.add_argument(
    "--entobench-build-dir", type=str, required=True, help="Path to the entobench build directory"
)
parser.add_argument(
    "--processes", type=int, default=1, help="Number of parallel processes to use"
)
parser.add_argument(
    "--output-dir", type=str, default="./", help="Directory to store output logs"
)

args = parser.parse_args()

def run_this(run_ball):
    run_dir = Path(run_ball['run_dir'])
    run_command = run_ball['run_command']
    print(f"Running in {run_dir.as_posix()} with command: {' '.join(run_command)}")
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "stdout.log", "w") as stdout_f, open(run_dir / "stderr.log", "w") as stderr_f:
        result = subprocess.run(
            run_command,
            cwd=run_dir,
            stdout=stdout_f,
            stderr=stderr_f
        )
    if result.returncode != 0:
        print(f"Run in {run_dir} failed with return code {result.returncode}")
    else:
        print(f"Run in {run_dir} completed successfully")
    return result.returncode

def main():
    gem5_base = Path(args.gem5_path)
    gem5_script = Path(args.gem5_script)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    entobench_build_dir = Path(args.entobench_build_dir)
    if not entobench_build_dir.is_dir():
        raise FileNotFoundError(f"Entobench build directory '{entobench_build_dir.as_posix()}' does not exist or is not a directory.")
    ubench_dir = entobench_build_dir / "benchmark/ubench/execution/bin"
    if not ubench_dir.is_dir():
        raise FileNotFoundError(f"Entobench ubench binary directory '{ubench_dir.as_posix()}' does not exist or is not a directory.")
    
    run_balls = []

    for bench in ubench_dir.iterdir():
        if not bench.is_file() or not os.access(bench.as_posix(), os.X_OK):
            raise FileNotFoundError(f"Benchmark binary '{bench.as_posix()}' does not exist or is not executable.")
        run_balls.append({
            "run_dir": Path(output_dir/bench.name).as_posix(),
            "run_command": [gem5_base.as_posix(),"-re", "-d", Path(f"{bench.name}-m5out").as_posix(), gem5_script.as_posix(), "--binary", bench.as_posix(), "--mode", "se"]
        })
    
    with Pool(processes=args.processes) as pool:
        results = pool.map(run_this, run_balls)

if __name__ == "__main__":
    main()
