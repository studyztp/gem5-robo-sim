IRQ override demo
=================

This small demo shows how to ship a vector table and weak default IRQ handlers in a library
and override a single IRQ handler (`IRQ5_Handler`) in an application.


Build (requires arm-none-eabi toolchain):

```bash
cd examples/irq_override_demo
make
```

The build produces `build/firmware.elf`.

To run in gem5 (example):

```bash
# Adjust gem5 binary path and script as needed for your setup
# Example using gem5's SE mode (ARM build):
# /path/to/gem5/build/ARM/gem5.opt configs/example/se.py -c build/firmware.elf
```

Notes:

- The demo focuses on linking and symbol overriding. It does not perform peripheral I/O.
- `IRQ5_Handler` in `app/app.c` demonstrates how the application replaces the weak handler
  from the library by providing a strong symbol with the same name.
