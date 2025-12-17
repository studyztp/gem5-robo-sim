from pathlib import Path

from board.MCU.cores.M4_core import CortexM4Processor
from board.MCU.cache.ART import ARTICache, ARTDCache

from m5.objects import (
    AddrRange,
    BadAddr,
    Process,
    SEWorkload,
    SimpleMemory,
    SrcClockDomain,
    System,
    VoltageDomain,
    NoncoherentXBar,
)

class STM32G4SEBoard:
    def __init__(self,
            clk_frequency: str = "100MHz",
            flash_memory_base: int = 0x08000000,
            flash_memory_size: str = "512KiB",
            sram1_base: int = 0x20000000,
            sram1_size: str = "80KiB",
            sram2_base: int = 0x20014000,
            sram2_size: str = "16KiB",
            pio_region_base: int = 0x40013000,
            pio_region_size: str = "1MiB",
            m5ops_base: int = 0x20020000):
        # create the system
        self.system = System()

        self.system.clk_domain = SrcClockDomain()
        self.system.clk_domain.clock = clk_frequency
        self.system.clk_domain.voltage_domain = VoltageDomain()
        self.system.mem_mode = "timing"
        # simulation exits when "work_begin" or "work_end" m5ops are executed
        self.system.exit_on_work_items = True
        # set cache line size to 32 bytes as in STM32G4
        self.system.cache_line_size = 32

        # ==== setup the CPU ====
        # single core Cortex-M4 with FPU
        processor = CortexM4Processor(num_cores=1, if_fpu=True)
        self.system.processor = processor
        # ==== end of CPU setup ====

        # ==== setup memory ranges ====
        # flash memory 512 KBytes
        self.flash_memory = AddrRange(start=flash_memory_base, size=flash_memory_size)
        # sram 1 has 80 KBytes
        self.sram1 = AddrRange(start=sram1_base, size=sram1_size)
        # sram 2 has 16 KBytes
        self.sram2 = AddrRange(start=sram2_base, size=sram2_size)
        # PIO region 16 MiBytes
        self.pio_region = AddrRange(start=pio_region_base, size=pio_region_size)
        # m5ops region 1 MiBytes
        self.m5op_region = AddrRange(start=m5ops_base, size="1MiB")
        # record memory ranges in system
        self.system.mem_ranges = [self.flash_memory, self.sram1, self.sram2, self.pio_region]
        # ==== end of memory ranges setup ====

        # ==== setup the memory bus ====
        # create a memory bus for the system
        self.system.membus = NoncoherentXBar(
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
        self.system.membus.badaddr_responder = BadAddr()
        self.system.membus.default = self.system.membus.badaddr_responder.pio

        # create Flash memory and connect it to the membus
        self.system.flash_memory = SimpleMemory()
        self.system.flash_memory.range = self.flash_memory
        self.system.flash_memory.port = self.system.membus.mem_side_ports
        self.system.flash_memory.latency = "40ns"
        self.system.flash_memory.bandwidth = "190MiB/s"

        # create SRAM 1 memory and connect it to the membus
        self.system.sram1 = SimpleMemory()
        self.system.sram1.range = self.sram1
        self.system.sram1.port = self.system.membus.mem_side_ports
        self.system.sram1.latency = "10ns"
        self.system.sram1.bandwidth = "400MiB/s"

        # create SRAM 2 memory and connect it to the membus
        self.system.sram2 = SimpleMemory()
        self.system.sram2.range = self.sram2
        self.system.sram2.port = self.system.membus.mem_side_ports
        self.system.sram2.latency = "10ns"
        self.system.sram2.bandwidth = "400MiB/s"

        # ART I-Cache+prefetcher and D-Cache
        self.system.icache = ARTICache(flash_addr_range=self.flash_memory)
        self.system.dcache = ARTDCache(flash_addr_range=self.flash_memory)

        # this part bypasses the cache hierarchy and connects the cores directly to the
        # membus
        for core in self.system.processor.get_cores():
            core.connect_icache(self.system.icache.cpu_side)
            core.connect_dcache(self.system.dcache.cpu_side)

            self.system.icache.mem_side = self.system.membus.cpu_side_ports
            self.system.dcache.mem_side = self.system.membus.cpu_side_ports
            # because Cortex M-class does not have an MMU, the walker ports are not
            # used. However, we still need to connect them to something, so we connect
            # them to the membus due to the tightly coupled nature of the MinorCPU with
            # the MMU
            core.connect_walker_ports(
                self.system.membus.cpu_side_ports, self.system.membus.cpu_side_ports
            )
            core.connect_interrupt()

        # set the self.system port for functional access from the simulator
        self.system.system_port = self.system.membus.cpu_side_ports
        # ==== end of memory bus setup ====

        self.system.m5ops_base = self.m5op_region.start

    def setup_workload(self, binary_path: Path):
        self.process = Process()
        self.process.executable = binary_path.as_posix()
        self.process.cmd = [binary_path.as_posix()]

        self.system.workload = SEWorkload.init_compatible(binary_path.as_posix())
        # set the process for the core
        self.system.processor.get_cores()[0].core.workload = [self.process]

    def setup_process_mappings(self):
        self.process.map(self.sram1.start, self.sram1.start, self.sram1.size())
        self.process.map(self.sram2.start, self.sram2.start, self.sram2.size())
        self.process.map(self.pio_region.start, self.pio_region.start, self.pio_region.size())
        self.process.map(self.m5op_region.start, self.m5op_region.start, self.m5op_region.size())

    def get_system(self):
        return self.system
        