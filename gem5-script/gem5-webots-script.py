import argparse
from pathlib import Path
import array, struct, ctypes
from bridge import _bridge as b
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
parser.add_argument(
    "--server-name", type=str, default="server0", help="Name of the bridge server"
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

# setupt the bridge server
print("Setup bridge server...")
print(f"Using server name: {server_name}")
client_pid, listen_fd = b.bridge_setup_server(server_name)
msg = b.bridge_wait_for_message(listen_fd, -1)
print(f"Bridge server setup complete, listen fd: {listen_fd}")
print(f"Received initial message: command={msg.command}, data={msg.data}")
n_init = len(msg.data)
print(f"Initial message length: {n_init} bytes")
if n_init > 0:
    print("Initial message bytes (hex):", msg.data[:64].hex())
n = len(msg.data) // 4
values = struct.unpack('<' + 'i'*n, msg.data)
print(f"Initial message data as {n} signed integers: {values}")
run_ahead_ticks = int(values[0]) * 10**9 # convert from milliseconds to picoseconds
ifComputing = False
print(f"Using run-ahead of {run_ahead_ticks} ps")

exit_event = m5.simulate(run_ahead_ticks)
exit_message = exit_event.getCause()

tick_left = run_ahead_ticks
start_tick = m5.curTick()

last_decision = None

def run_ahead_ended():
    global run_ahead_ticks, client_pid, listen_fd, ifComputing, tick_left, start_tick
    # print("Run-ahead period ended, waiting for message from client...")
    msg = b.bridge_wait_for_message(listen_fd, -1)
    # print(f"Received message: command={msg.command}, data_len={len(msg.data)}")
    if len(msg.data) > 0:
        # print("fs_board: message first bytes (hex):", msg.data[:64].hex())
        if len(msg.data) % 8 == 0:
            try:
                nd = len(msg.data) // 8
                vals = struct.unpack('<' + 'd' * nd, msg.data)
                # print(f"fs_board: unpacked {nd} doubles:", vals)
            except Exception as e:
                print("fs_board: failed to unpack doubles:", e)
        else:
            print("fs_board: message length not multiple of 8, cannot unpack as doubles")
    arr = array.array('B', msg.data)
    if system.bridge_io.ifDone():
        print("Bridge IO indicates computing is done")
        output_data = system.bridge_io.getOutputData()
        output_data_size = system.bridge_io.getOutputDataSize()
        print(f"Output data size: {output_data_size} bytes")
        # output_data is a sequence of bytes (ints 0..255). Trim to reported
        # output_size and convert to a bytes object for the bridge message.
        trimmed = output_data[:output_data_size]
        msg = b.Message()
        msg.command = b.COMMAND.COMPUTE_RESPONSE
        msg.data = bytes(trimmed)
        b.bridge_send_message(listen_fd, msg)
        print(f"Sent COMPUTE_RESPONSE message with {output_data_size} bytes of data")
    else:
        output_data = [ctypes.c_float(0.0), ctypes.c_float(0.0)]  # zero
        output_data_size = ctypes.sizeof(ctypes.c_float) * len(output_data)
        msg = b.Message()
        msg.command = b.COMMAND.COMPUTE_RESPONSE
        msg.data = struct.pack('<' + 'f'*len(output_data), *[x.value for x in output_data])
        b.bridge_send_message(listen_fd, msg)
        # print(f"Sent COMPUTE_RESPONSE message with {output_data_size} bytes of zero data")
    if not ifComputing:
        # msg.data is bytes (pybind Message.data returns bytes)
        # Convert to unsigned-byte array explicitly
        # Debug: show first bytes

        # Pass the array (sequence of ints) to the C++ method
        ok = system.bridge_io.updateInputData(arr)
        print(f"Updated bridge input data buffer with {len(arr)} bytes, updateInputData returned {ok}")
        print("Print out the bytes sent to Bridge IO device (hex):")
        for i in range(len(arr)):
            print(f"{arr[i]:02x}", end=" ")
        print()
        system.bridge_io.raiseInterrupt()
        print("Raised Bridge IO interrupt to notify core")
        ifComputing = True
    tick_left = run_ahead_ticks
    start_tick = m5.curTick()

def bridge_io_interrupt_work_done():
    global ifComputing, tick_left, start_tick
    ifComputing = False
    system.bridge_io.clearInterrupt()
    tick_left = run_ahead_ticks - (m5.curTick() - start_tick)
    print(f"{m5.curTick()}:{tick_left}\n")

while not exit_message == "exiting with last active thread context":
    # print(f"Simulation stopped with exit message: {exit_message}")
    if exit_message == "BridgeIODevice signaled done.":
        bridge_io_interrupt_work_done()
    else:
        run_ahead_ended()
    # print("Resuming simulation...")
    # print(f"{m5.curTick()}:{tick_left}\n")
    exit_event = m5.simulate(tick_left)
    exit_message = exit_event.getCause()

print("Simulation ended cleanly")
