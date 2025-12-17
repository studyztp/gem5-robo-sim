import argparse
from pathlib import Path
import array, struct, ctypes
import m5
from m5.objects import Root
from boards.fs_STM32G4 import STM32G4FSBoard

import sys, os

# add current directory to sys.path to allow imports from it
sys.path.append(os.getcwd())

parser = argparse.ArgumentParser(
    description="Run a gem5 simulation with the demo stm32g4 MCU board in FS"
        " mode."
)
parser.add_argument(
    "--binary", type=str, required=True, help="Path to the binary to run"
)
args = parser.parse_args()

binary_path = Path(args.binary)
if not binary_path.is_file():
    raise FileNotFoundError(f"Binary file '{binary_path.as_posix()}' does not "
                            "exist.")

server_name = args.server_name

board = STM32G4FSBoard()
board.setup_workload(binary_path)
system = board.get_system()

root = Root(full_system=True, system=system)

m5.instantiate()

runtimes = []
begin_tick = 0
event_track = 0

# ==== define workbegin and workend reaction ====
def workbegin_handler():
    global begin_tick, event_track
    print(f"workbegin {event_track} called")
    # reset stats at workbegin
    m5.stats.reset()
    print("Reset stats")
    begin_tick = m5.curTick()
    print("Start Debug Flags")
    # m5.debug.flags["Fetch"].enable()
    # m5.debug.flags["CachePort"].enable()
    # m5.debug.flags["ARTCache"].enable()
    m5.debug.flags["ExecAll"].enable()

def workend_handler():
    global begin_tick, runtimes, event_track
    print(f"workend {event_track} called")
    # dump stats at workend
    m5.stats.dump()
    print("Dumped stats")
    end_tick = m5.curTick()
    runtime = end_tick - begin_tick
    runtimes.append(runtime)
    print(f"Runtime for this region: {runtime} ticks, "
                                            f"{runtime / 1000000000000:.6f} s")
    event_track += 1
    print("Stop Debug Flags")
    # m5.debug.flags["Fetch"].disable()
    # m5.debug.flags["CachePort"].disable()
    # m5.debug.flags["ARTCache"].disable()
    m5.debug.flags["ExecAll"].disable()
# ==== end of workbegin and workend reaction ====

# ==== start the simulation ====
print("Beginning simulation!")
exit_event = m5.simulate()
cause = exit_event.getCause()
print(f"Exit cause: {cause}")
while cause in ["workbegin", "workend"]:
    if cause == "workbegin":
        workbegin_handler()
    elif cause == "workend":
        workend_handler()
    exit_event = m5.simulate()
    cause = exit_event.getCause()
# ==== end of simulation ====

avg_tick = sum(runtimes) / len(runtimes) if len(runtimes) > 0 else 0
print(f"Average runtime over {len(runtimes)} region(s): {avg_tick} ticks, "
      f"{avg_tick / 1000000000000:.6f} s")

