import argparse
from pathlib import Path

from cores.M4_core import CortexM4Processor
from cache.ART import ARTICache, ARTDCache

import m5
from m5.objects import (
    AddrRange,
    BadAddr,
    Process,
    Root,
    SEWorkload,
    SimpleMemory,
    SrcClockDomain,
    System,
    VoltageDomain,
    NoncoherentXBar,
    DummySPI,
)
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.components.processors.cpu_types import CPUTypes

parser = argparse.ArgumentParser(
    description="Run a gem5 simulation with the demo stm32g4 MCU board in SE"
        " mode."
)
parser.add_argument(
    "--binary1", type=str, required=True, help="Path to the binary to run"
)
parser.add_argument(
    "--binary2", type=str, required=True, help="Path to the second binary to run"
)
parser.add_argument(
    "--processor", type=str, default="cortex-m4",
    choices=["cortex-m4", "simple-OOO"], help="Type of processor to use"
)
args = parser.parse_args()

binary1_path = Path(args.binary1)
if not binary1_path.is_file():
    raise FileNotFoundError(f"Binary file '{binary1_path.as_posix()}' does not "
                            "exist.")

binary2_path = Path(args.binary2)
if not binary2_path.is_file():
    raise FileNotFoundError(f"Binary file '{binary2_path.as_posix()}' does not "
                            "exist.")

system = System()

system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "100MHz"
system.clk_domain.voltage_domain = VoltageDomain()
system.mem_mode = "timing"
# simulation exits when "work_begin" or "work_end" m5ops are executed
system.exit_on_work_items = True
# set cache line size to 32 bytes as in STM32G4
system.cache_line_size = 32

# ==== setup the CPU ====
# single core Cortex-M4 with FPU
if args.processor == "cortex-m4":
    processor = CortexM4Processor(num_cores=1, if_fpu=True)
else:
    processor = SimpleProcessor(cpu_type=CPUTypes.O3, num_cores=1, isa=ISA.ARM)
system.processor = processor
# ==== end of CPU setup ====

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
pio_region = AddrRange(start=0x40013000, size="1MiB")
# record memory ranges in system
system.mem_ranges = [flash_memory, sram1, sram2, pio_region]
# ==== end of memory ranges setup ====

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

# create Flash memory and connect it to the membus
system.flash_memory = SimpleMemory()
system.flash_memory.range = flash_memory
system.flash_memory.port = system.membus.mem_side_ports
system.flash_memory.latency = "40ns"
system.flash_memory.bandwidth = "190MiB/s"

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

# create dummySPI
system.dummy_spi = DummySPI(
    target_address=sram1.start,
    target_cpu=system.processor.get_cores()[0].core,
    interrupt_thread_id=1,
    move_delay_cycles=100,
    grid_width=10,
    grid_height=10,
    start_x=0,
    start_y=0,
    pio_addr=pio_region.start,
    pio_size=pio_region.size(),
    pio_latency="10ns"
)
system.dummy_spi.pio = system.membus.mem_side_ports
system.dummy_spi.dma = system.membus.cpu_side_ports

# ART I-Cache+prefetcher and D-Cache
system.icache = ARTICache(flash_addr_range=flash_memory)
system.dcache = ARTDCache(flash_addr_range=flash_memory)

# this part bypasses the cache hierarchy and connects the cores directly to the
# membus
for core in system.processor.get_cores():
    core.connect_icache(system.icache.cpu_side)
    core.connect_dcache(system.dcache.cpu_side)

    system.icache.mem_side = system.membus.cpu_side_ports
    system.dcache.mem_side = system.membus.cpu_side_ports
    # because Cortex M-class does not have an MMU, the walker ports are not
    # used. However, we still need to connect them to something, so we connect
    # them to the membus due to the tightly coupled nature of the MinorCPU with
    # the MMU
    core.connect_walker_ports(
        system.membus.cpu_side_ports, system.membus.cpu_side_ports
    )
    core.connect_interrupt()

# set the system port for functional access from the simulator
system.system_port = system.membus.cpu_side_ports

# ==== end of memory bus setup ====

# ==== setup the process ====
# create the process
process1 = Process()
process1.executable = binary1_path.as_posix()
process1.cmd = [binary1_path.as_posix()]

process2 = Process()
process2.executable = binary2_path.as_posix()
process2.cmd = [binary2_path.as_posix()]
process2.pid = 200
process2.ppid = 1
process2.pgid = 200

system.workload = SEWorkload.init_compatible(binary1_path.as_posix())

system.m5ops_base = m5op_region.start

# set the process for the core
system.processor.get_cores()[0].core.workload = [process1, process2]
system.processor.get_cores()[0].core.numThreads = 2

system.multi_thread = True

# ==== end of process setup ====

# ==== setup the simulation ====
# create the root of the system
root = Root(full_system=False, system=system)
# instantiate the system
m5.instantiate()
# ==== end of simulation setup ====

process1.map(sram1.start, sram1.start, sram1.size())
process1.map(sram2.start, sram2.start, sram2.size())
process1.map(m5op_region.start, m5op_region.start , m5op_region.size())
process1.map(pio_region.start, pio_region.start, pio_region.size())

process2.map(sram1.start, sram1.start, sram1.size())
process2.map(sram2.start, sram2.start, sram2.size())
process2.map(m5op_region.start, m5op_region.start , m5op_region.size())
process2.map(pio_region.start, pio_region.start, pio_region.size())

print(f"Currently at {Path().absolute()}")

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
    # m5.debug.flags["ExecAll"].enable()

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
    # m5.debug.flags["ExecAll"].disable()
# ==== end of workbegin and workend reaction ====

# ==== start the simulation ====
print("Beginning simulation!")
exit_event = m5.simulate()
cause = exit_event.getCause()
print(f"Exit cause: {cause}")
# while cause in ["workbegin", "workend"]:
#     if cause == "workbegin":
#         workbegin_handler()
#     elif cause == "workend":
#         workend_handler()
#     exit_event = m5.simulate()
#     cause = exit_event.getCause()
# ==== end of simulation ====

avg_tick = sum(runtimes) / len(runtimes) if len(runtimes) > 0 else 0
print(f"Average runtime over {len(runtimes)} region(s): {avg_tick} ticks, "
      f"{avg_tick / 1000000000000:.6f} s")

