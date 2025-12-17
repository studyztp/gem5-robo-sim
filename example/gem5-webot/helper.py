import argparse
import os
import time
import subprocess
import pathlib
from pathlib import Path

import bridge._bridge as br

parser = argparse.ArgumentParser(
    description="Run the bridge helper server to connect gem5 and Webots."
)
parser.add_argument(
    "--gem5-path", type=str, required=True, help="Path to the gem5 executable"
)
parser.add_argument(
    "--gem5-script", type=str, required=True, help="Path to the gem5 script"
)
parser.add_argument(
    "--gem5-binary", type=str, required=True, help="Path to the binary to run in gem5"
)
parser.add_argument(
    "--webots-path", type=str, required=True, help="Path to the Webots executable"
)
parser.add_argument(
    "--webots-world", type=str, required=True, help="Path to the Webots world file"
)
parser.add_argument(
    "--output-dir", type=str, default="./", help="Directory to store output logs"
)

args = parser.parse_args()

def main():
    # mapping of client_name -> server_name
    client_to_server = {
        "R0": "gem5-0",
        "R1": "gem5-1",
    }

    listen_fd = br.bridge_setup_helper_server_socket()
    print(f"Helper listening on fd {listen_fd}")

    # start server and client subprocesses (they will connect to the helper)
    webots_base = Path(args.webots_path)
    webots_args = ["--minimize",
        args.webots_world,
        "--stdout",
        "--stderr"
    ]

    gem5_base = Path(args.gem5_path)
    gem5_args = [
        args.gem5_script,
        "--binary",
        args.gem5_binary,
        "--server-name"
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def start_executable(path, args, friendly_name):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{friendly_name} not found at {path}")
        if not os.access(path, os.X_OK):
            raise PermissionError(f"{friendly_name} at {path} is not executable")
        return subprocess.Popen([str(path)] + args)

    # start the external programs directly (do NOT invoke them with the Python interpreter)
    webots_proc = start_executable(webots_base, webots_args, "webots")
    # small delay so server registers shortly after starting
    time.sleep(0.1)
    gem5_0_proc = start_executable(gem5_base, ["-re", "-d", f"{output_dir.as_posix()}/gem5-0-m5out"] + gem5_args + ["gem5-0"], "gem5-0")
    time.sleep(0.1)
    gem5_1_proc = start_executable(gem5_base, ["-re", "-d", f"{output_dir.as_posix()}/gem5-1-m5out"] + gem5_args + ["gem5-1"], "gem5-1")
    print("Started server and client; entering helper loop")
    try:
        br.bridge_helper_server_loop(listen_fd, client_to_server)
    except KeyboardInterrupt:
        print("Interrupted, shutting down children...")
    finally:
        br.bridge_close_helper_server_socket(listen_fd)

    print("Waiting for children to exit")
    # # ensure children are terminated cleanly
    # procs = [("webots", webots_proc), ("gem5-0", gem5_0_proc), ("gem5-1", gem5_1_proc)]
    # for name, proc in procs:
    #     if proc is None:
    #         continue
    #     try:
    #         if proc.poll() is None:
    #             proc.terminate()
    #             try:
    #                 proc.wait(timeout=5)
    #             except subprocess.TimeoutExpired:
    #                 proc.kill()
    #                 proc.wait()
    #     except Exception as e:
    #         print(f"Error terminating {name}: {e}")
            

    # # collect exit codes
    # rc_webots = webots_proc.returncode
    # rc_gem5_0 = gem5_0_proc.returncode
    # rc_gem5_1 = gem5_1_proc.returncode
    # print(f"webots exit: {rc_webots}, gem5-0 exit: {rc_gem5_0}, gem5-1 exit: {rc_gem5_1}")

    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
