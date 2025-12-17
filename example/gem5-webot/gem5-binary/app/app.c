// main.c — GIC-only path, matching the vector table’s GIC rule (index == GIC ID)

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*ISR)(void);

/* BridgeIO address */
#define BRIDGE_IO_BASE 0x88000000u
#define BRIDGE_IO_GO             (*(volatile uint32_t *)(BRIDGE_IO_BASE))
#define BRIDGE_IO_REG_DONE      (*(volatile uint32_t *)(BRIDGE_IO_BASE + sizeof(uint32_t)))
#define BRIDGE_IO_REG_INPUT_START  (*(volatile uint32_t *)(BRIDGE_IO_BASE + sizeof(uint32_t) * 2))
#define BRIDGE_IO_REG_INPUT_SIZE   (*(volatile uint32_t *)(BRIDGE_IO_BASE + sizeof(uint32_t) * 3))
#define BRIDGE_IO_REG_OUTPUT_START (*(volatile uint32_t *)(BRIDGE_IO_BASE + sizeof(uint32_t) * 4))
#define BRIDGE_IO_REG_OUTPUT_SIZE  (*(volatile uint32_t *)(BRIDGE_IO_BASE + sizeof(uint32_t) * 5))

/* Vector table from your library (placed in .isr_vector) */
extern ISR const g_vectors[];

/* ---- GICv2 CPU interface (per gem5 VE defaults) ---- */
// #ifndef GICC_BASE
#define GICC_BASE 0x2C002000u   // CPU interface (default RealView/VExpress value)
// #endif

/* Distributor base (GICD) typically sits 0x1000 below the CPU interface on
    many RealView/VExpress setups. Keep an explicit define so the bring-up
    below can access distributor registers. */
// #ifndef GICD_BASE
#define GICD_BASE 0x2C001000u
// #endif

#define GICC_IAR   (*(volatile uint32_t *)(GICC_BASE + 0x0C))  // Interrupt Acknowledge
#define GICC_EOIR  (*(volatile uint32_t *)(GICC_BASE + 0x10))  // End of Interrupt

int bump_count = 0;
const int max_velocity = 10;

/* Strong IRQ5 handler (GIC ID 32+5 = 37) */
void IRQ5_Handler(void) {
    puts("Custom INT Handler Invoked!");
    printf("Bridge IO 'go' register: %u\n", BRIDGE_IO_GO);
    printf("Read Bridge IO 'done' register: %u\n", BRIDGE_IO_REG_DONE);
    printf("Bridge IO input buffer at 0x%x, size %u\n",
           BRIDGE_IO_REG_INPUT_START, BRIDGE_IO_REG_INPUT_SIZE);
    printf("Bridge IO output buffer at 0x%x, size %u\n",
           BRIDGE_IO_REG_OUTPUT_START, BRIDGE_IO_REG_OUTPUT_SIZE);
    printf("Reading from the input buffer and write to output buffer:\n");
    uintptr_t in_f = (uintptr_t)(BRIDGE_IO_REG_INPUT_START);
    size_t in_size = BRIDGE_IO_REG_INPUT_SIZE;
    uintptr_t out_f = (uintptr_t)(BRIDGE_IO_REG_OUTPUT_START);
    int* out_f_int = (int *)out_f;

    int bumped = *((int *)in_f);
    if (bumped)
        bump_count = 15;  // set bump count if bumped
    if (bump_count == 0) {
        out_f_int[0] = max_velocity;
        out_f_int[1] = max_velocity;
    } else {
        if (bump_count >= 7) {
            // backup
            out_f_int[0] = -max_velocity;
            out_f_int[1] = -max_velocity;
        } else {
            // turn right
            out_f_int[0] = -max_velocity/2;
            out_f_int[1] = max_velocity;
        }
        bump_count--;
    }
    printf("Output velocities: left=%d right=%d\n", out_f_int[0], out_f_int[1]);

    // Acknowledge handled interrupt and signal end-of-interrupt
    // record the size of output data
    BRIDGE_IO_REG_OUTPUT_SIZE = 2 * sizeof(int);
    // Signal done
    BRIDGE_IO_REG_DONE = 1u;
}

/* Minimal GIC dispatcher: acknowledge, call handler by vector index (= GIC ID), EOI */
static inline int gic_dispatch_once(void) {
    uint32_t iar = GICC_IAR;           // read current interrupt
    uint32_t int_id = iar & 0x3FFu;    // GICv2: ID in bits [9:0]
    /* Diagnostic: print the raw IAR and the extracted ID so we can
       observe what the GIC presents to the CPU (useful to debug why
       the handler isn't being invoked). Keep prints short to avoid
       cluttering serial output. */
    printf("[gic_dispatch] IAR=0x%08x int_id=%u\n", iar, int_id);

    if (int_id == 0x3FFu) return 0;    // spurious / no pending

    ISR h = g_vectors[int_id];         // vector index == GIC ID (your rule)
    if (h) h();                        // call the handler (Thumb bit set by linker)

    GICC_EOIR = iar;                   // signal end-of-interrupt
    return 1;
}

int main(void) {
    puts("Starting (GIC rule, no NVIC). Bringing up GIC and waiting for interrupts...");
    /* Minimal GIC bring-up for GICv2: enable distributor, enable SPI 37
       (our IRQ5 -> GIC ID 32+5 = 37), set CPU interface priority mask and
       enable the CPU interface. This avoids relying on an external
       bootloader to configure the GIC. */
    {
        /* GICD registers */
        volatile uint32_t *gicd_ctlr = (volatile uint32_t *)(GICD_BASE + 0x000);      // GICD_CTLR
        /* We'll enable a wide range of interrupts so the firmware doesn't
           need to know the exact SPI number the platform uses. This avoids
           touching ITARGETSR (which earlier runs showed can fault in the
           simulator). We enable ISENABLER words 0..3 (covering IDs 0..127).
           On RealView/GICv2 these registers are at GICD_BASE + 0x100 + 4*n. */
        for (uint32_t n = 0; n < 4u; ++n) {
            volatile uint32_t *gicd_isenabler = (volatile uint32_t *)(GICD_BASE + 0x100 + 4u * n);
            *gicd_isenabler = 0xFFFFFFFFu; /* enable 32 interrupts at a time */
        }
        /* Ensure writes commit (tiny delay) */
        for (volatile int i = 0; i < 100; ++i) __asm__ __volatile__("nop");
        /* Enable the distributor last */
        *gicd_ctlr = 1u;
    }

    /* GICC registers */
    {
        volatile uint32_t *gicc_pmr  = (volatile uint32_t *)(GICC_BASE + 0x04);
        volatile uint32_t *gicc_ctlr = (volatile uint32_t *)(GICC_BASE + 0x00);

        /* Accept all priorities */
        *gicc_pmr = 0xFFu;
        /* Enable CPU interface */
        *gicc_ctlr = 1u;
          /* Do NOT enable CPU IRQs here. Keep IRQs masked so the polling
              dispatcher continues to run and will observe the GIC IAR when
              the SPI is pending. Enabling IRQs causes the CPU to take the
              exception vector path which this firmware does not rely on. */
          /* IRQs intentionally left disabled to use polling dispatch */
    }

    for (;;) {
        // Do any background work here...
        /* Keep a polling fallback: if IRQs aren't taken for some reason
           the polling dispatcher can still service interrupts. */
        (void)gic_dispatch_once();     // poll & dispatch one IRQ if pending
        __asm__ __volatile__("nop");
    }
    // not reached
}

/* C-level IRQ entry called from the assembly IRQ_Handler. This performs the
 * same acknowledge/dispatch/EOI sequence as the polling path. */
void c_irq_entry(void)
{
    uint32_t iar = GICC_IAR;           // read current interrupt
    uint32_t int_id = iar & 0x3FFu;    // GICv2: ID in bits [9:0]
    if (int_id == 0x3FFu) return;      // spurious / no pending

    /* Call vector table mapping (vector index == GIC ID) */
    extern ISR const g_vectors[];
    ISR h = g_vectors[int_id];
    if (h) h();

    GICC_EOIR = iar;                   // signal end-of-interrupt
}
