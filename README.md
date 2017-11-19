# PeekPoke

PeekPoke is a serial protocol for reading and writing a Propeller's hub RAM.

The Propeller implementation here is designed to be entirely cog-contained after launch. It supports the writeBytes, writeLongs, and readLongs commands -- the other commands can be composed from these. Theoretically, it can operate at 3Mbps, but refer to the notes on the PropCR page about problems at this speed.

This project depends on PropCR: https://github.com/chris-siedell/PropCR

## Example 

PC side:
```cpp
#include "PeekPoke.hpp"

int main() {
  PeekPoke pp("/dev/cu.usbserial-XXXX");  
  std::vector<uint32_t> longs;
  
  // after this call longs contains the two long values at hub addresses 32000 and 32004
  pp.readLongs(32000, 2, longs);
  
  std::vector<uint8_t> bytes;
  bytes.push_back(0x05);
  
  // after this call hub address 30000 has value 0x05
  pp.writeBytes(30000, bytes);
}
```
Propeller side:
```spin
obj

  peekpoke : "PeekPoke"
  
pub main

  'use pins 30/31 at 115200 bps, and device address 1 (Crow protocol parameter)
  peekpoke.setParams(31, 30, 115200, 1)
  
  'after the following call the PeekPoke instance is running and the hub space can be repurposed
  peekpoke.new
```
