cmake_minimum_required(VERSION 3.16)
project(ts LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(ts ./src/tsc/main.cpp)