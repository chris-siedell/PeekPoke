# PeekPoke

PeekPoke is a utility for reading and writing a Propeller's hub RAM from a PC.
It consists of two parts: a python package for sending commands from the PC, and
a PASM program for responding to commands. The PASM program is entirely
cog-contained after launch.

The Python package may be installed using `pip install peekpoke`, or by downloading
from PyPI.org at <https://pypi.org/project/peekpoke/>.

PeekPoke allows the serial timings to be changed remotely (this feature can be
disabled). By default, if a break condition is detected the serial parameters will
be reset to their last known good values.

If the payloadExec feature is enabled PeekPoke will allow the PC to execute
arbitrary code, effectively allowing any command that can be implemented in 65
registers (plus the 16 register static buffer).

By default, all features of PeekPoke except payloadExec are enabled. There are
Spin methods that can enable and disable some of the features.

Each PeekPoke instance requires a unique address on the serial line (addresses
may be 1 to 31, 1 is the default). PeekPoke uses port 112 by default, but this
may be changed.

The following methods are available to change the default settings before launch.
Some must be called in a particular sequence.

- `setPins(rxPin, txPin)`
- `setBaudrate(baudrate)`
- `setInterbyteTimeoutInMS(milliseconds)` - if called, MUST follow setBaudrate
- `setInterbyteTimeoutInBitPeriods(count)` - if called, MUST follow setBaudrate
- `setRecoveryTimeInMS(milliseconds)`
- `setRecoveryTimeInBitPeriods(count)` - if called, MUST follow setBaudrate
- `setBreakThresholdInMS(milliseconds)` - MUST be called if setRecoveryTime\* is called
- `setAddress(address)`
- `setPort(port)`
- `enableWriteHub`
- `disableWriteHub`
- `enableSetSerialParams`
- `disableSetSerialParams`
- `enablePayloadExec`
- `disablePayloadExec`
- `enableBreakDetection`
- `disableBreakDetection`
  
If the recovery time is set, then `setBreakThresholdInMS` must be called afterwards
in order to recalculate the timings constants, regardless if the threshold has changed.

Calling the above methods has no effect on already launched instances.

`start` takes an argument that is passed to the new instance using the PAR register.
The PC can use the `get_par` command to obtain its value. 

`start` will not return until the new instance is completely loaded, so calling code
may immediately prepare to launch another instance.

