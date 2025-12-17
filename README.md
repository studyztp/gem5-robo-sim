# gem5-robo-sim

A simulation framework integrating gem5 with Webots for robotic systems on STM32G4 microcontroller boards. This project supports both System Call Emulation (SE) and Full System (FS) simulation modes.

## Table of Contents

- [Building Tools](#building-tools)
  - [gem5](#gem5)
  - [Webots](#webots)
  - [Bridge Library](#bridge-library)
  - [Entobench](#entobench)
- [Running Simulations](#running-simulations)
  - [SE Mode: Microbenchmarks](#se-mode-microbenchmarks)
  - [FS Mode: gem5 + Webots](#fs-mode-gem5--webots)
- [Troubleshooting](#troubleshooting)

## Building Tools

### gem5

The gem5 simulator is used for cycle-accurate simulation of ARM Cortex-M4 processors.

**Install dependencies (Ubuntu/Debian):**

```bash
sudo apt-get install -y \
    build-essential scons python3-dev git pre-commit zlib1g zlib1g-dev \
    libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
    libboost-all-dev libhdf5-serial-dev python3-pydot python3-venv python3-tk mypy \
    m4 libcapstone-dev libpng-dev libelf-dev pkg-config wget cmake doxygen clang-format
```

**Build gem5:**

```bash
cd gem5
scons build/ARM/gem5.opt -j$(nproc)
```

Build time: ~30-60 minutes depending on your system.

### Webots

Webots is an open-source robot simulator used for full-system simulation with physical interactions.

**Install dependencies (Ubuntu/Debian):**

```bash
sudo apt-get install -y \
    git cmake swig libglu1-mesa-dev libglib2.0-dev libfreeimage3 libfreetype6-dev \
    libxml2-dev libboost-dev libssh-gcrypt-dev libzip-dev libreadline-dev pbzip2 \
    wget zip unzip python3 python3-pip libopenal-dev
```

**Set up environment variables:**

```bash
# Optional: Disable saving screen perspective changes
export WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=1

# Optional: Allow modifying Webots installation files
export WEBOTS_ALLOW_MODIFY_INSTALLATION=1

# Required: Set Webots home directory
export WEBOTS_HOME=$PWD/webots
```

**Build Webots:**

```bash
python3 -m venv venv
source venv/bin/activate
cd webots
make -j$(nproc)
```

### Bridge Library

The bridge library provides Unix-domain socket communication between different processes, such as gem5 and Webots.

**Install dependencies (Ubuntu/Debian):**

```bash
sudo apt-get install -y build-essential cmake g++ make python3 python3-dev python3-pip
```

**Install Python dependencies:**

```bash
pip install pybind11 setuptools wheel
```

**Build C++ library:**

```bash
cd bridge
mkdir -p build
cmake -S . -B build
cmake --build build --parallel
```

**Build Python bindings:**

```bash
cd bridge/python

# Install in development mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

**Verify installation:**

```bash
python3 -c "import bridge; print('Bridge library installed successfully')"
```

### Entobench

Entobench provides microbenchmarks for evaluating embedded system performance.

**Build Entobench:**

```bash
cd ento-bench
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=gem5-cmake/arm-gem5.cmake
cmake --build build
```

This will generate benchmark binaries in `ento-bench/build/benchmark/`.

## Running Simulations

### SE Mode: Microbenchmarks

Syscall Emulation (SE) mode allows running bare-metal binaries with Linux system emulation.

**Run a single benchmark:**

```bash
export WORKDIR=$PWD

# Example: run add-16-bits-pc-stream-1 benchmark
gem5/build/ARM/gem5.opt -re -d add-16-bits-pc-stream-1-m5out \
    gem5-script/run-binary.py \
    --binary ento-bench/build/benchmark/ubench/execution/bin/add-16-bits-pc-stream-1 \
    --mode se
```

Results will be saved in `add-16-bits-pc-stream-1-m5out/` with:
- `stats.txt` - Performance statistics
- `config.ini` - Simulation configuration
- `simout.txt` / `simerr.txt` - Simulation output/errors

**Run all benchmarks in parallel:**

```bash
export WORKDIR=$PWD

python3 $WORKDIR/example/gem5-ubench/helper.py \
    --gem5-path $WORKDIR/gem5/build/ARM/gem5.opt \
    --gem5-script $WORKDIR/gem5-script/run-binary.py \
    --entobench-build-dir $WORKDIR/ento-bench/build \
    --processes 4 \
    --output-dir $WORKDIR/ubench-m5out
```

**Helper script options:**

| Option | Description |
|--------|-------------|
| `--gem5-path` | Path to the gem5 executable |
| `--gem5-script` | Path to the gem5 Python configuration script |
| `--entobench-build-dir` | Path to the entobench build directory |
| `--processes` | Number of parallel simulations (default: 1) |
| `--output-dir` | Directory to store all output logs |

### FS Mode: gem5 + Webots

Full System (FS) mode runs gem5 with Webots for realistic robot simulation with accurate timing.

**Prerequisites:**
- gem5 built with ARM support
- Webots installed and built
- Bridge library Python bindings installed
- Firmware binary compiled (ELF format, not raw binary)

**Run co-simulation:**

```bash
export WORKDIR=$PWD
source venv/bin/activate

python3 example/gem5-webot/helper.py \
    --gem5-path $WORKDIR/gem5/build/ARM/gem5.opt \
    --gem5-script $WORKDIR/gem5-script/gem5-webots-script.py \
    --gem5-binary $WORKDIR/example/gem5-webot/gem5-binary/build/firmware.elf \
    --webots-path $WORKDIR/webots/webots \
    --webots-world $WORKDIR/example/gem5-webot/webot-models/worlds/plane.wbt \
    --output-dir $WORKDIR/gem5-webots-output
```

**Helper script options:**

| Option | Description |
|--------|-------------|
| `--gem5-path` | Path to the gem5 executable |
| `--gem5-script` | Path to the gem5-webots integration script |
| `--gem5-binary` | Path to the firmware binary (must be ELF format) |
| `--webots-path` | Path to the Webots executable |
| `--webots-world` | Path to the Webots world file (.wbt) |
| `--output-dir` | Directory to store output logs (optional) |

**Note:** The firmware binary must be in ELF format, not raw binary (.bin). If you only have a .bin file, you need the corresponding .elf file.

## Troubleshooting

### gem5 Issues

**Segmentation fault in `resetCPSR()`:**
- Ensure you're using `--mode se` for SE binaries and `--mode fs` for FS binaries
- Check that the system is properly initialized

**"Could not load kernel file" error:**
- Verify the binary path is correct
- Ensure the binary is in ELF format (use `file` command to check)
- For raw binaries, convert to ELF or use a different loader

**Memory address range overlapping:**
- This has been fixed in the board configuration
- If you see this and using the SE board, ensure `se_STM32G4.py` doesn't define duplicate memory regions

### Webots Issues

**Webots won't start:**
- Check that `WEBOTS_HOME` is set correctly
- Verify all dependencies are installed
- Try running `webots --version` to test the installation

**Bridge connection fails:**
- Ensure the bridge Python library is installed: `python3 -c "import bridge"`
- Check that Unix domain sockets are supported on your system
- Verify no other process is using the socket path

### Build Issues

**C++17 compilation errors:**
- Ensure your GCC version is 7.0 or later: `g++ --version`
- Try setting explicitly: `export CXX=g++-9` (or newer)

**Python import errors:**
- Activate the virtual environment: `source venv/bin/activate`
- Reinstall the bridge library: `cd bridge/python && pip install -e .`

**Out of memory during build:**
- Reduce parallel jobs: `scons build/ARM/gem5.opt -j4` (instead of `$(nproc)`)
- Close unnecessary applications
- Consider using a machine with more RAM (16GB+ recommended for gem5)
