CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
CFLAGS = -mcpu=cortex-m4 -mthumb -O2 -g --specs=nosys.specs --specs=nano.specs -fno-exceptions --data-sections -static -mfloat-abi=hard -mfpu=fpv4-sp-d16 -march=armv7e-m
LDFLAGS = -nostartfiles -Wl,--gc-sections -T linker/stm32g4.ld

BUILD_DIR = build

ALL_OBJS = $(BUILD_DIR)/syscall_wrapper.o $(BUILD_DIR)/vector_table.o $(BUILD_DIR)/app.o

.PHONY: all clean
all: $(BUILD_DIR)/firmware.elf

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/syscall_wrapper.o: lib/syscall_wrapper.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/vector_table.o: lib/vector_table.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/app.o: app/app.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/firmware.elf: $(ALL_OBJS)
	$(CC) $(CFLAGS) $(ALL_OBJS) $(LDFLAGS) -o $@
	$(OBJCOPY) -O binary $@ $(BUILD_DIR)/firmware.bin || true

clean:
	rm -rf $(BUILD_DIR)
