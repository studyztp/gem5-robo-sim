# gem5-robo-sim

## Building tools

### gem5

```bash
cd gem5
scons build/ARM/gem5.opt -j$(nproc)
```

### webots

Ubuntu dependencies:

```
git cmake swig libglu1-mesa-dev libglib2.0-dev libfreeimage3 libfreetype6-dev libxml2-dev libboost-dev libssh-gcrypt-dev libzip-dev libreadline-dev pbzip2 wget zip unzip python3 python3-pip libopenal-dev
```

Environment variables:

```bash
#######################################################
# Edit these WEBOTS environment variables when needed #
#######################################################

export WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=1  # If defined, Webots will not save screen specific perspective changes when closed.
export WEBOTS_ALLOW_MODIFY_INSTALLATION=1                 # If defined, you are allowed to modify files in the Webots home using Webots.

#########################################################################
# These environment variables are necessaries to compile and run Webots #
#########################################################################

export WEBOTS_HOME=$PWD/webots  # Defines the path to Webots home.
```

commands:

```bash
python3 -m venv venv
source venv/bin/activate
cd webots
make -j$(nproc)
```

### bridge

dependencies:

```text
build-essential cmake g++ make python3 python3-dev python3-pip
```

python dependencies:

```text
pybind11 setuptools wheel
```

c++ library:

```bash
cd bridge
cmake -S $PWD -B build
cmake --build build --parallel
```

python library:

```bash
cd bridge/python

# Install in development mode (editable)
pip install -e .

# Or install normally
pip install .
```

## Run STM32G4 board on gem5 SE mode with gem5-se-use microbenchmarks in Entobench

```bash
cd ento-bench
cmake -S $PWD -B $PWD/build -DCMAKE_TOOLCHAIN_FILE=gem5-cmake/arm-gem5.cmake
cmake --build build 
```

Example of running `add-16-bits-pc-stream-1`:

```bash
gem5/build/ARM/gem5.opt -re -d add-16-bits-pc-stream-1-m5out gem5-script/run-binary.py  --binary ento-bench/build/benchmark/ubench/execution/bin/add-16-bits-pc-stream-1 --mode=se
```

gem5 experiment result will be in `add-16-bits-pc-stream-1-m5out`.

Use helper script to run all:

```bash
export WORKDIR=$PWD
python3 $WORKDIR/example/gem5-ubench/helper.py --gem5-path $WORKDIR/gem5/build/ARM/gem5.opt --gem5-script $WORKDIR/gem5-script/run-binary.py --entobench-build-dir $WORKDIR/ento-bench/build --processes 2 --output-dir $WORKDIR/ubench-m5out
```

What the helper script takes:

```bash
usage: helper.py [-h] --gem5-path GEM5_PATH --gem5-script GEM5_SCRIPT --entobench-build-dir ENTOBENCH_BUILD_DIR [--processes PROCESSES]
                 [--output-dir OUTPUT_DIR]

Run all microbenchmarks in gem5 with entobench

options:
  -h, --help            show this help message and exit
  --gem5-path GEM5_PATH
                        Path to the gem5 executable
  --gem5-script GEM5_SCRIPT
                        Path to the gem5 script
  --entobench-build-dir ENTOBENCH_BUILD_DIR
                        Path to the entobench build directory
  --processes PROCESSES
                        Number of parallel processes to use
  --output-dir OUTPUT_DIR
                        Directory to store output logs
```

## Run STM32G4 board on gem5 FS mode with Webots

```bash
export WORKDIR=$PWD
source venv/bin/activate
python3 example/gem5-webot/helper.py --gem5-path $WORKDIR/gem5/build/ARM/gem5.opt --gem5-script $WORKDIR/gem5-script/gem5-webots-script.py --gem5-binary $WORKDIR/example/gem5-webot/gem5-binary/build/firmware.elf --webots-path $WORKDIR/webots/webots --webots-world $WORKDIR/example/gem5-webot/webot-models/worlds/plane.wbt
```

What the script takes:

```
usage: helper.py [-h] --gem5-path GEM5_PATH --gem5-script GEM5_SCRIPT --gem5-binary GEM5_BINARY --webots-path WEBOTS_PATH --webots-world
                 WEBOTS_WORLD [--output-dir OUTPUT_DIR]

Run the bridge helper server to connect gem5 and Webots.

options:
  -h, --help            show this help message and exit
  --gem5-path GEM5_PATH
                        Path to the gem5 executable
  --gem5-script GEM5_SCRIPT
                        Path to the gem5 script
  --gem5-binary GEM5_BINARY
                        Path to the binary to run in gem5
  --webots-path WEBOTS_PATH
                        Path to the Webots executable
  --webots-world WEBOTS_WORLD
                        Path to the Webots world file
  --output-dir OUTPUT_DIR
                        Directory to store output logs
```
