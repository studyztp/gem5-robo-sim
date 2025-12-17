#include <stdint.h>
#include <stddef.h>

/* Place the AArch32 CPU exception vector table as instructions in the
 * .vectors section. We emit the branch instructions and a tiny IRQ
 * stub using inline assembly here so the entire firmware stays in C
 * source files (no separate .S file). The IRQ stub calls the C entry
 * point `c_irq_entry` implemented in app.c. */
asm(
    ".section .vectors, \"ax\", %progbits\n"
    ".align 2\n"
    ".global _vectors_start\n"
    "_vectors_start:\n"
    "    b Reset_Handler\n"
    "    b Undefined_Handler\n"
    "    b SWI_Handler\n"
    "    b PrefetchAbort_Handler\n"
    "    b DataAbort_Handler\n"
    "    b Reserved_Handler\n"
    "    b IRQ_Handler\n"
    "    b FIQ_Handler\n"
);

/* IRQ handler stub (assembly). Save a small register set, call the C
 * entrypoint `c_irq_entry`, restore registers and return from IRQ. */
asm(
    ".text\n"
    ".align 2\n"
    ".global IRQ_Handler\n"
    "IRQ_Handler:\n"
    "    stmfd sp!, {r0-r3, r12, lr}\n"
    "    bl c_irq_entry\n"
    "    ldmfd sp!, {r0-r3, r12, lr}\n"
    "    subs pc, lr, #4\n"
);

/* Weak aliases for other exception labels that branch to Default_Handler
 * if not provided elsewhere. Keep them global so linked code can override
 * specific handlers if needed. */
asm(
    ".weak Undefined_Handler\n"
    ".weak SWI_Handler\n"
    ".weak PrefetchAbort_Handler\n"
    ".weak DataAbort_Handler\n"
    ".weak Reserved_Handler\n"
    ".weak FIQ_Handler\n"
    "Undefined_Handler: b Default_Handler\n"
    "SWI_Handler: b Default_Handler\n"
    "PrefetchAbort_Handler: b Default_Handler\n"
    "DataAbort_Handler: b Default_Handler\n"
    "Reserved_Handler: b Default_Handler\n"
    "FIQ_Handler: b Default_Handler\n"
);

/* --------------------------------------------------------------------------
 * Cortex-M4 + AArch32 rules with GIC-style external IDs
 * - Vector indices 0..15: standard M4 core exceptions
 * - Vector indices 16..31: reserved (kept to preserve M-profile layout)
 * - Vector index 32 + N: external interrupt N (GIC ID = table index)
 * Only minimal startup code is kept. No polling helpers, no debug prints.
 * --------------------------------------------------------------------------*/

/* Linker-provided symbols */
extern uint32_t _estack;
extern uint32_t _sidata; /* flash: init values for .data */
extern uint32_t _sdata;  /* ram: start of .data */
extern uint32_t _edata;  /* ram: end of .data */
extern uint32_t _sbss;   /* ram: start of .bss */
extern uint32_t _ebss;   /* ram: end of .bss */

/* Default handler loops forever so unexpected IRQs are obvious. */
void Default_Handler(void) { while (1) {} }

/* Core exception prototypes */
void Reset_Handler(void);
void NMI_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void)   __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SVC_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void DebugMon_Handler(void)   __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void)     __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void)    __attribute__((weak, alias("Default_Handler")));

/* External IRQ handlers (32 slots by default; extend if you need more) */
#ifndef NVIC_IRQ_COUNT
#define NVIC_IRQ_COUNT 32u
#endif

#define EXTERNAL_VECTOR_BASE 32u

void IRQ0_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ1_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ2_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ3_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ4_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ5_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ6_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ7_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ8_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ9_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void IRQ10_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ11_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ12_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ13_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ14_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ15_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ16_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ17_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ18_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ19_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ20_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ21_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ22_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ23_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ24_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ25_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ26_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ27_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ28_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ29_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ30_Handler(void) __attribute__((weak, alias("Default_Handler")));
void IRQ31_Handler(void) __attribute__((weak, alias("Default_Handler")));

/* Vector mapping table used by the firmware's dispatcher.
 * This is NOT the CPU exception vector table. For AArch32 we place
 * real branch instructions at the exception vector offsets (see
 * aarch32_vectors.S). The firmware keeps a separate array of C
 * function pointers (g_vectors) that map external interrupt IDs to
 * IRQ handlers. */
const void * const g_vectors[EXTERNAL_VECTOR_BASE + NVIC_IRQ_COUNT] = {
    /*  0 */ (void*)&_estack,     /* Initial MSP */
    /*  1 */ Reset_Handler,
    /*  2 */ NMI_Handler,
    /*  3 */ HardFault_Handler,
    /*  4 */ MemManage_Handler,
    /*  5 */ BusFault_Handler,
    /*  6 */ UsageFault_Handler,
    /*  7 */ 0,
    /*  8 */ 0,
    /*  9 */ 0,
    /* 10 */ 0,
    /* 11 */ SVC_Handler,
    /* 12 */ DebugMon_Handler,
    /* 13 */ 0,
    /* 14 */ PendSV_Handler,
    /* 15 */ SysTick_Handler,

    /* 16..31 reserved to preserve M-profile layout */
    /* 16 */ Default_Handler, /* reserved */
    /* 17 */ Default_Handler,
    /* 18 */ Default_Handler,
    /* 19 */ Default_Handler,
    /* 20 */ Default_Handler,
    /* 21 */ Default_Handler,
    /* 22 */ Default_Handler,
    /* 23 */ Default_Handler,
    /* 24 */ Default_Handler,
    /* 25 */ Default_Handler,
    /* 26 */ Default_Handler,
    /* 27 */ Default_Handler,
    /* 28 */ Default_Handler,
    /* 29 */ Default_Handler,
    /* 30 */ Default_Handler,
    /* 31 */ Default_Handler,

    /* External interrupts: vector index == GIC ID */
    /* 32 */ IRQ0_Handler,
    /* 33 */ IRQ1_Handler,
    /* 34 */ IRQ2_Handler,
    /* 35 */ IRQ3_Handler,
    /* 36 */ IRQ4_Handler,
    /* 37 */ IRQ5_Handler,
    /* 38 */ IRQ6_Handler,
    /* 39 */ IRQ7_Handler,
    /* 40 */ IRQ8_Handler,
    /* 41 */ IRQ9_Handler,
    /* 42 */ IRQ10_Handler,
    /* 43 */ IRQ11_Handler,
    /* 44 */ IRQ12_Handler,
    /* 45 */ IRQ13_Handler,
    /* 46 */ IRQ14_Handler,
    /* 47 */ IRQ15_Handler,
    /* 48 */ IRQ16_Handler,
    /* 49 */ IRQ17_Handler,
    /* 50 */ IRQ18_Handler,
    /* 51 */ IRQ19_Handler,
    /* 52 */ IRQ20_Handler,
    /* 53 */ IRQ21_Handler,
    /* 54 */ IRQ22_Handler,
    /* 55 */ IRQ23_Handler,
    /* 56 */ IRQ24_Handler,
    /* 57 */ IRQ25_Handler,
    /* 58 */ IRQ26_Handler,
    /* 59 */ IRQ27_Handler,
    /* 60 */ IRQ28_Handler,
    /* 61 */ IRQ29_Handler,
    /* 62 */ IRQ30_Handler,
    /* 63 */ IRQ31_Handler,
};

/* Naked reset stub that sets SP, r0, r1 exactly per AArch32 pattern,
 * then branches to C reset. This preserves the original calling
 * convention while allowing main() to be Thumb.
 */
void Reset_Handler(void) __attribute__((naked));
void Reset_Handler(void)
{
    __asm__ volatile (
        "ldr   sp, =_estack    \n\t"
        "movs  r0, #0          \n\t"
        "movs  r1, #0          \n\t"
        "b     Reset_Handler_C \n\t"
    );
}

/* C reset: copy .data, zero .bss, then call main().
 * main() is allowed to be Thumb (as on Cortex-M); the compiler ensures
 * BL to Thumb entry. No semihosting, no extras.
 */
void Reset_Handler_C(void)
{

    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) { *dst++ = *src++; }
    for (dst = &_sbss; dst < &_ebss; ) { *dst++ = 0u; }

    extern int main(void);
    (void)main();

    /* If main returns, trap */
    while (1) {}
}
