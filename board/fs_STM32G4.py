from board.MCU.cores.M4_core import CortexM4Processor
from board.MCU.cache.ART import ARTICache, ARTDCache
from pathlib import Path

from m5.objects import (
    ArmFsWorkload,
    AddrRange,
    ArmSemihosting,
    BadAddr,
    Bridge,
    Cache,
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

class STM32G4FSBoard:
    def __init__(self):
        self.system = ArmSystem()

        self.system.clk_domain = SrcClockDomain()
        self.system.clk_domain.clock = "100MHz"
        self.system.clk_domain.voltage_domain = VoltageDomain(voltage="1.0V")
        self.system.voltage_domain = VoltageDomain(voltage="1.0V")
        self.system.mem_mode = "timing"
        # simulation exits when "work_begin" or "work_end" m5ops are executed
        self.system.exit_on_work_items = True
        # set cache line size to 32 bytes
        # STM32G4 has 8-byte wide cache lines, but gem5 requires a minimum of 32-byte
        # TODO: investigate if we can change this requirement in gem5. 
        # Currently, using cache_line_size=8 triggers major memory leaks.
        self.system.cache_line_size = 32

        # ==== setup the platform and release ====
        # set the system port for functional access from the simulator
        platform = VExpress_GEM5_V1()
        release = ArmDefaultRelease()
        self.system.release = release
        self.system.realview = platform
        self.system.iobus = IOXBar()
        self.system.terminal = Terminal()
        self.system.vncserver = VncServer()

        # == Setup the processor ==
        processor = CortexM4Processor(num_cores=1, if_fpu=True)
        self.system.processor = processor

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
        self.system.mem_ranges = [sram1, sram2, gic_region]

        for mem_range in self.system.realview._mem_regions:
            self.system.mem_ranges.append(
                AddrRange(start=mem_range.start, size=mem_range.size())
            )
            print(f"Added memory range: {hex(mem_range.start)} - {hex(mem_range.start + mem_range.size())}")

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
        # the max. routing table size needs to be set to a higher value for HBM2 stack
        # self.system.membus.max_routing_table_size = 2048

        # setup semihosting
        self.system.semihosting = ArmSemihosting(
            stdin = "stdin",
            stdout = "stdout",
            stderr = "stderr",
        )
        # create Flash memory and connect it to the membus
        # self.system.flash_memory = SimpleMemory()
        # self.system.flash_memory.range = flash_memory
        # self.system.flash_memory.port = self.system.membus.mem_side_ports
        # self.system.flash_memory.latency = "40ns"
        # self.system.flash_memory.bandwidth = "190MiB/s"

        # create SRAM 1 memory and connect it to the membus
        self.system.sram1 = SimpleMemory()
        self.system.sram1.range = sram1
        self.system.sram1.port = self.system.membus.mem_side_ports
        self.system.sram1.latency = "10ns"
        self.system.sram1.bandwidth = "400MiB/s"

        # create SRAM 2 memory and connect it to the membus
        self.system.sram2 = SimpleMemory()
        self.system.sram2.range = sram2
        self.system.sram2.port = self.system.membus.mem_side_ports
        self.system.sram2.latency = "10ns"
        self.system.sram2.bandwidth = "400MiB/s"

        # connect the IO bridge and IO cache to the membus
        self.system.iobridge = Bridge(delay="50ns", ranges=self.system.mem_ranges)
        self.system.iocache = Cache(
            assoc = 8,
            tag_latency = 50,
            data_latency = 50,
            response_latency = 50,
            mshrs = 20,
            size = "1KiB",
            tgts_per_mshr = 12,
            addr_ranges = flash_memory
        )
        self.system.dmabridge = Bridge(delay="50ns", 
            ranges=self.system.mem_ranges)

        self.system.iobridge.mem_side_port = self.system.iobus.cpu_side_ports
        self.system.iobridge.cpu_side_port = self.system.membus.mem_side_ports
        self.system.iocache.mem_side = self.system.membus.cpu_side_ports
        self.system.iocache.cpu_side = self.system.iobus.mem_side_ports
        self.system.dmabridge.mem_side_port = self.system.membus.cpu_side_ports
        self.system.dmabridge.cpu_side_port = self.system.iobus.mem_side_ports
        if hasattr(self.system.realview.gic, "cpu_addr"):
            self.system.gic_cpu_addr = self.system.realview.gic.cpu_addr
        self.system.realview.attachOnChipIO(self.system.membus, self.system.iobridge)
        self.system.realview.attachIO(self.system.iobus)
        self.system.system_port = self.system.membus.cpu_side_ports
        # This is where the flash memory is connected in the real STM32G4 board
        self.system.realview.flash0.latency = "40ns"
        self.system.realview.flash0.bandwidth = "190MiB/s"
        self.system.realview.flash0.range = flash_memory

        # ART I-Cache+prefetcher and D-Cache
        self.system.icache = ARTICache(flash_addr_range=flash_memory)
        self.system.dcache = ARTDCache(flash_addr_range=flash_memory)

        self.system.cpu_to_icache_xbar = NoncoherentXBar(
            # 128-bit crossbar by default
            width = 16,

            # Make the crossbar add zero cycles for requests/responses
            frontend_latency = 0,
            forward_latency  = 0,
            response_latency = 0,

            # Remove header occupancy cost too (default is 1)
            header_latency = 0,
        )
        self.system.cpu_to_icache_xbar.badaddr_responder = BadAddr()
        self.system.cpu_to_icache_xbar.default = self.system.cpu_to_icache_xbar.badaddr_responder.pio
        self.system.cpu_to_icache_dmabridge = Bridge(delay="0ns", 
            ranges=self.system.mem_ranges)
        self.system.cpu_to_dcache_xbar = NoncoherentXBar(
            # 128-bit crossbar by default
            width = 16,

            # Make the crossbar add zero cycles for requests/responses
            frontend_latency = 0,
            forward_latency  = 0,
            response_latency = 0,

            # Remove header occupancy cost too (default is 1)
            header_latency = 0,
        )
        self.system.cpu_to_dcache_xbar.badaddr_responder = BadAddr()
        self.system.cpu_to_dcache_xbar.default = self.system.cpu_to_dcache_xbar.badaddr_responder.pio
        self.system.cpu_to_dcache_dmabridge = Bridge(delay="0ns", 
            ranges=self.system.mem_ranges)

        # this part bypasses the cache hierarchy and connects the cores directly to the
        # membus
        for core in self.system.processor.get_cores():
            core.connect_icache(self.system.cpu_to_icache_xbar.cpu_side_ports)
            core.connect_dcache(self.system.cpu_to_dcache_xbar.cpu_side_ports)

            self.system.icache.cpu_side = self.system.cpu_to_icache_xbar.mem_side_ports
            self.system.dcache.cpu_side = self.system.cpu_to_dcache_xbar.mem_side_ports
            self.system.cpu_to_icache_dmabridge.cpu_side_port = self.system.cpu_to_icache_xbar.mem_side_ports
            self.system.cpu_to_dcache_dmabridge.cpu_side_port = self.system.cpu_to_dcache_xbar.mem_side_ports
            self.system.icache.mem_side = self.system.membus.cpu_side_ports
            self.system.dcache.mem_side = self.system.membus.cpu_side_ports
            self.system.cpu_to_icache_dmabridge.mem_side_port = self.system.membus.cpu_side_ports
            self.system.cpu_to_dcache_dmabridge.mem_side_port = self.system.membus.cpu_side_ports
            # because Cortex M-class does not have an MMU, the walker ports are not
            # used. However, we still need to connect them to something, so we connect
            # them to the membus due to the tightly coupled nature of the MinorCPU with
            # the MMU
            core.connect_walker_ports(
                self.system.membus.cpu_side_ports, self.system.membus.cpu_side_ports
            )
            core.connect_interrupt()

        self.system.auto_reset_addr = True
        if hasattr(self.system.realview.gic, "gicv4"):
            self.system.realview.gic.gicv4 = False


        self.system.highest_el_is_64 = False

        # == PIO devices ==
        BRIDGE_SPI_NUM = 37
        self.system.bridge_int_pin = ArmSPI(num=BRIDGE_SPI_NUM)
        self.system.bridge_io = BridgeIODevice(
            pio_addr=pio_region.start,
            pio_size=pio_region.size(),
            input_data_buffer_size=256,
            output_data_buffer_size=256,
            isa="Arm",
            go=True,
            interrupt_pin=self.system.bridge_int_pin
        )
        self.system.bridge_io.pio = self.system.membus.mem_side_ports

    def setup_workload(self, binary_path: Path):
        class ArmBaremetal(ArmFsWorkload):
            # copied from configs/example/arm/workloads.py
            """Baremetal workload"""

            dtb_addr = 0

            def __init__(self, obj, system, **kwargs):
                super().__init__(**kwargs)

                self.object_file = obj
        self.system.workload = ArmBaremetal(binary_path.as_posix(), self.system)

    def get_system(self):
        return self.system
