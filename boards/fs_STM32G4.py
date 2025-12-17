import argparse
from pathlib import Path
from cores.M4_core import CortexM4Processor
from cache.ART import ARTICache, ARTDCache
import array, struct, ctypes

from bridge import _bridge as b

import m5
from m5.objects import (
    ArmFsWorkload,
    AddrRange,
    ArmSemihosting,
    BadAddr,
    Bridge,
    Cache,
    Process,
    Root,
    SEWorkload,
    SimpleMemory,
    SrcClockDomain,
    ArmSystem,
    Terminal,
    VoltageDomain,
    VncServer,
    NoncoherentXBar,
    VExpress_GEM5_V1,
    ArmDefaultRelease,
    IOXBar,
    BridgeIODevice, 
    ArmSPI
)
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.components.processors.cpu_types import CPUTypes

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
# boot_path = Path(args.boot)
# if not boot_path.is_file():
#     raise FileNotFoundError(f"Bootloader file '{boot_path.as_posix()}' does not "
#                             "exist.")
server_name = args.server_name

class ArmBaremetal(ArmFsWorkload):
    # copied from configs/example/arm/workloads.py
    """Baremetal workload"""

    dtb_addr = 0

    def __init__(self, obj, system, **kwargs):
        super().__init__(**kwargs)

        self.object_file = obj

system = ArmSystem()

system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "100MHz"
system.clk_domain.voltage_domain = VoltageDomain(voltage="1.0V")
system.voltage_domain = VoltageDomain(voltage="1.0V")
system.mem_mode = "timing"
# simulation exits when "work_begin" or "work_end" m5ops are executed
system.exit_on_work_items = True
# set cache line size to 32 bytes as in STM32G4
system.cache_line_size = 32

# ==== setup the platform and release ====
# set the system port for functional access from the simulator
platform = VExpress_GEM5_V1()
release = ArmDefaultRelease()
system.release = release
system.realview = platform
system.iobus = IOXBar()
system.terminal = Terminal()
system.vncserver = VncServer()

# == Setup the processor ==
processor = CortexM4Processor(num_cores=1, if_fpu=True)
system.processor = processor

# ==== setup memory ranges ====
# flash memory 512 KBytes
flash_memory = AddrRange(start=0x08000000, size="512KiB")
# sram 1 has 80 KBytes
sram1 = AddrRange(start=0x20000000, size="80KiB")
# sram 2 has 16 KBytes
sram2 = AddrRange(start=0x20014000, size="16KiB")
# m5op region 1 MiBytes
m5op_region = AddrRange(start=0x20020000, size="1MiB")
# PIO region 16 MiBytes
pio_region = AddrRange(start=0x88000000, size="1MiB")
# GIC region
gic_region = AddrRange(start=0x2C000000, size="4MiB")
# record memory ranges in system
system.mem_ranges = [sram1, sram2, gic_region]

for mem_range in system.realview._mem_regions:
    system.mem_ranges.append(
        AddrRange(start=mem_range.start, size=mem_range.size())
    )
    print(f"Added memory range: {hex(mem_range.start)} - {hex(mem_range.start + mem_range.size())}")

# ==== setup the memory bus ====
# create a memory bus for the system
system.membus = NoncoherentXBar(
    # copy from SystemXBar
    # 128-bit crossbar by default
    width = 16,

    # A handful pipeline stages for each portion of the latency
    # contributions.
    frontend_latency = 0,
    forward_latency = 0,
    response_latency = 0
)

# bad address responder so when the CPU accesses an unmapped address, the
# simulation will panic
system.membus.badaddr_responder = BadAddr()
system.membus.default = system.membus.badaddr_responder.pio
# the max. routing table size needs to be set to a higher value for HBM2 stack
# system.membus.max_routing_table_size = 2048

# setup semihosting
system.semihosting = ArmSemihosting(
    stdin = "stdin",
    stdout = "stdout",
    stderr = "stderr",
)
# create Flash memory and connect it to the membus
# system.flash_memory = SimpleMemory()
# system.flash_memory.range = flash_memory
# system.flash_memory.port = system.membus.mem_side_ports
# system.flash_memory.latency = "40ns"
# system.flash_memory.bandwidth = "190MiB/s"

# create SRAM 1 memory and connect it to the membus
system.sram1 = SimpleMemory()
system.sram1.range = sram1
system.sram1.port = system.membus.mem_side_ports
system.sram1.latency = "10ns"
system.sram1.bandwidth = "400MiB/s"

# create SRAM 2 memory and connect it to the membus
system.sram2 = SimpleMemory()
system.sram2.range = sram2
system.sram2.port = system.membus.mem_side_ports
system.sram2.latency = "10ns"
system.sram2.bandwidth = "400MiB/s"

# connect the IO bridge and IO cache to the membus
system.iobridge = Bridge(delay="50ns", ranges=system.mem_ranges)
system.iocache = Cache(
    assoc = 8,
    tag_latency = 50,
    data_latency = 50,
    response_latency = 50,
    mshrs = 20,
    size = "1KiB",
    tgts_per_mshr = 12,
    addr_ranges = flash_memory
)
system.dmabridge = Bridge(delay="50ns", 
    ranges=system.mem_ranges)

system.iobridge.mem_side_port = system.iobus.cpu_side_ports
system.iobridge.cpu_side_port = system.membus.mem_side_ports
system.iocache.mem_side = system.membus.cpu_side_ports
system.iocache.cpu_side = system.iobus.mem_side_ports
system.dmabridge.mem_side_port = system.membus.cpu_side_ports
system.dmabridge.cpu_side_port = system.iobus.mem_side_ports
if hasattr(system.realview.gic, "cpu_addr"):
    system.gic_cpu_addr = system.realview.gic.cpu_addr
system.realview.attachOnChipIO(system.membus, system.iobridge)
system.realview.attachIO(system.iobus)
system.system_port = system.membus.cpu_side_ports

system.realview.flash0.latency = "40ns"
system.realview.flash0.bandwidth = "190MiB/s"
system.realview.flash0.range = flash_memory

# ART I-Cache+prefetcher and D-Cache
system.icache = ARTICache(flash_addr_range=flash_memory)
system.dcache = ARTDCache(flash_addr_range=flash_memory)

system.cpu_to_icache_xbar = NoncoherentXBar(
    # 128-bit crossbar by default
    width = 16,

    # Make the crossbar add zero cycles for requests/responses
    frontend_latency = 0,
    forward_latency  = 0,
    response_latency = 0,

    # Remove header occupancy cost too (default is 1)
    header_latency = 0,
)
system.cpu_to_icache_xbar.badaddr_responder = BadAddr()
system.cpu_to_icache_xbar.default = system.cpu_to_icache_xbar.badaddr_responder.pio
system.cpu_to_icache_dmabridge = Bridge(delay="0ns", 
    ranges=system.mem_ranges)
system.cpu_to_dcache_xbar = NoncoherentXBar(
    # 128-bit crossbar by default
    width = 16,

    # Make the crossbar add zero cycles for requests/responses
    frontend_latency = 0,
    forward_latency  = 0,
    response_latency = 0,

    # Remove header occupancy cost too (default is 1)
    header_latency = 0,
)
system.cpu_to_dcache_xbar.badaddr_responder = BadAddr()
system.cpu_to_dcache_xbar.default = system.cpu_to_dcache_xbar.badaddr_responder.pio
system.cpu_to_dcache_dmabridge = Bridge(delay="0ns", 
    ranges=system.mem_ranges)

# this part bypasses the cache hierarchy and connects the cores directly to the
# membus
for core in system.processor.get_cores():
    core.connect_icache(system.cpu_to_icache_xbar.cpu_side_ports)
    core.connect_dcache(system.cpu_to_dcache_xbar.cpu_side_ports)

    system.icache.cpu_side = system.cpu_to_icache_xbar.mem_side_ports
    system.dcache.cpu_side = system.cpu_to_dcache_xbar.mem_side_ports
    system.cpu_to_icache_dmabridge.cpu_side_port = system.cpu_to_icache_xbar.mem_side_ports
    system.cpu_to_dcache_dmabridge.cpu_side_port = system.cpu_to_dcache_xbar.mem_side_ports
    system.icache.mem_side = system.membus.cpu_side_ports
    system.dcache.mem_side = system.membus.cpu_side_ports
    system.cpu_to_icache_dmabridge.mem_side_port = system.membus.cpu_side_ports
    system.cpu_to_dcache_dmabridge.mem_side_port = system.membus.cpu_side_ports
    # because Cortex M-class does not have an MMU, the walker ports are not
    # used. However, we still need to connect them to something, so we connect
    # them to the membus due to the tightly coupled nature of the MinorCPU with
    # the MMU
    core.connect_walker_ports(
        system.membus.cpu_side_ports, system.membus.cpu_side_ports
    )
    core.connect_interrupt()

system.auto_reset_addr = True
if hasattr(system.realview.gic, "gicv4"):
    system.realview.gic.gicv4 = False


system.highest_el_is_64 = False

# ==== setup the workload ====

system.workload = ArmBaremetal(binary_path.as_posix(), system)

# # Install workload (kernel) and tell platform about bootloader
# system.workload = ArmBaremetal(binary_path.as_posix(), system)
# # Tell the platform to use our bootloader (VExpress helper will set load offsets)
# # Instead of calling the platform helper (which has several overloads),
# # set the workload bootloader fields directly to mirror
# # RealView.setupBootLoader(...)
# system.workload.boot_loader = boot_path.as_posix()
# # Use flash base (0x0800_0000) as the kernel load offset so the kernel
# # image maps into the `flash_memory` region defined above.
# system.workload.load_addr_mask = 0
# system.workload.load_addr_offset = 0x08000000
# system.workload.dtb_addr = system.workload.load_addr_offset + 0x00800000
# # Use 0x200000 as this is the maximum size allowed for a DTB
# system.workload.initrd_addr = system.workload.dtb_addr + 0x200000
# system.workload.cpu_release_addr = system.workload.dtb_addr - 8

# == PIO devices ==
BRIDGE_SPI_NUM = 37
system.bridge_int_pin = ArmSPI(num=BRIDGE_SPI_NUM)
system.bridge_io = BridgeIODevice(
    pio_addr=pio_region.start,
    pio_size=pio_region.size(),
    input_data_buffer_size=256,
    output_data_buffer_size=256,
    isa="Arm",
    go=True,
    interrupt_pin=system.bridge_int_pin
)
system.bridge_io.pio = system.membus.mem_side_ports

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
