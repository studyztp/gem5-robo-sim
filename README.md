# gem5-robo-sim


## Build gem5-use microbenchmarks in Entobench

```bash
cd ento-bench
cmake -S $PWD -B $PWD/build -DCMAKE_TOOLCHAIN_FILE=gem5-cmake/arm-gem5.cmake
```
