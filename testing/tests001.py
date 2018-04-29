# tests001.py
# 29 April 2018
# Chris Siedell
# source: https://github.com/chris-siedell/PeekPoke
# python: https://pypi.org/project/peekpoke/
# homepage: http://siedell.com/projects/PeekPoke/


# Warning: the break condition will be sent during this test. This may
#  affect other devices on the serial line.


import sys
import time
import random
from peekpoke import PeekPoke
from crow.admin import CrowAdmin


if len(sys.argv) < 2:
    sys.exit("Please provide the serial port name as a command line argument.")

serial_port_name = sys.argv[1]

REF_CLKFREQ = 80000000
INIT_BAUD = 115200
LOWER_BAUD = 57600

start_time = time.perf_counter()

p = PeekPoke(serial_port_name)

print("PeekPoke Tests 001")
print(" Serial port: " + serial_port_name)
print(" Assumptions:")
print("  - it is safe to send a break condition,")
print("  - setup001.spin is running,")
print("  - the reference values have not been overwritten,")
print("  - all features besides payloadExec are enabled,")
print("  - the PeekPoke service is at address " + str(p.address) + " and port " + str(p.port) + ",")
print("  - the Propeller and the PC can communicate at " + str(INIT_BAUD) + " and " + str(LOWER_BAUD) + " bps,")
print("  - the Propeller's clock frequency is " + str(REF_CLKFREQ) + " Hz.")
print(" These tests do not overwrite the reference values.")
print(" Testing should take about 14 seconds.")
print(" ...")


# === Service Check ===

# Verify that a Crow device exists at the given serial port and address,
#  and that it is running a PeekPoke service on the expected Crow port.
admin = CrowAdmin(serial_port_name, default_address=p.address)
admin.ping()
info = admin.get_port_info(p.port)
if not info['is_open']:
    raise RuntimeError("The PeekPoke service port is closed.")
if 'service_identifier' in info:
    if info['service_identifier'] != "PeekPoke":
        raise RuntimeError("There is an unexpected service at the PeekPoke port (" + info['service_identifier'] + ").")
else:
    raise RuntimeError("The service at the PeekPoke port unexpectedly does not have an identifier.")


# === Token Tests ===

# A non-zero token indicates that the reference values have been overwritten. In that
#  case the program will need to be reloaded.

k = p.get_token()
if k != 0:
    raise RuntimeError("Please reboot or reload the Propeller so that a fresh instance of setup001.spin is running.")

v = p.set_token_bytes(b'\xa0\xb1\xc2\xd3')
if v != b'\x00\x00\x00\x00':
    raise RuntimeError()
v = p.get_token()
if v != 3552752032:
    raise RuntimeError()
v = p.get_token(byteorder='big')
if v != 2696004307:
    raise RuntimeError()

v = p.set_token_bytes(b'\xff\xff', use_padding=True)
if v != b'\xa0\xb1\xc2\xd3':
    raise RuntimeError()
v = p.get_token()
if v != 65535:
    raise RuntimeError()

v = p.set_token(305419896, byteorder='big')
if v != 4294901760:
    raise RuntimeError()
v = p.get_token_bytes()
if v != b'\x12\x34\x56\x78':
    raise RuntimeError()

v= p.set_token(-1, signed=True)
if v != 2018915346:
    raise RuntimeError()
v = p.get_token(signed=True)
if v != -1:
    raise RuntimeError()
v = p.get_token_bytes()
if v != b'\xff\xff\xff\xff':
    raise RuntimeError()

try:
    p.set_token_bytes(b'01234')
    raise RuntimeError()
except ValueError:
    # expect ValueError since five byte provided
    pass

try:
    p.set_token_bytes(b'xff', use_padding=False)
    raise RuntimeError()
except ValueError:
    # expect ValueError since one byte provided and no padding selected
    pass

v = p.get_token()
if v != 4294967295:
    raise RuntimeError()

v = p.set_token(0)
if v != 4294967295:
    raise RuntimeError()
v = p.get_token()
if v != 0:
    raise RuntimeError()


# === get_par Test ===

# par points to the address table, which holds the addresses to various
#  reference items in hub memory.
par = p.get_par()

# get_addr obtains the address of the given item in the address table.
def get_addr(index):
    return p.get_int(par + 2*index, 2)


# === String Reading Tests ===

# Check the copyright message in the ROM.
v = p.get_str(65297, 30)
if v != "Copyright 2005  Parallax, Inc.":
    raise RuntimeError()

# Items at indices 0 to 12 in the address table are NUL-terminated strings.

v = p.get_str(get_addr(0), 20)
if v != "setup001":
    raise RuntimeError("This test requires that the Propeller be running setup001.spin.")

def verify_table_str(index, reference):
    v = p.get_str(get_addr(index), 5000)
    if v != reference:
        raise RuntimeError()

verify_table_str(1, "")
verify_table_str(2, "a")
verify_table_str(3, "hi")
verify_table_str(4, "cat")
verify_table_str(5, "plop")
verify_table_str(6, "tulip")
verify_table_str(7, "cheese")
verify_table_str(8, "library")
verify_table_str(9, "elephant")
verify_table_str(10, "processor")

gettysburg = "\tFour score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.\n\tNow we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure. We are met on a great battle-field of that war. We have come to dedicate a portion of that field, as a final resting place for those who here gave their lives that that nation might live. It is altogether fitting and proper that we should do this.\n\tBut, in a larger sense, we can not dedicate -- we can not consecrate -- we can not hallow -- this ground. The brave men, living and dead, who struggled here, have consecrated it, far above our poor power to add or detract. The world will little note, nor long remember what we say here, but it can never forget what they did here. It is for us the living, rather, to be dedicated here to the unfinished work which they who fought here have thus far so nobly advanced. It is rather for us to be here dedicated to the great task remaining before us -- that from these honored dead we take increased devotion to that cause for which they gave the last full measure of devotion -- that we here highly resolve that these dead shall not have died in vain -- that this nation, under God, shall have a new birth of freedom -- and that government of the people, by the people, for the people, shall not perish from the earth."

verify_table_str(11, gettysburg)

v = p.get_str(get_addr(11), 5)
if v != "\tFour":
    raise RuntimeError()

v = p.get_str(get_addr(12), 5000, encoding='utf_8')
if v != "Ⓐ":
    raise RuntimeError()

v = p.get_str(get_addr(8), 3, nul_terminated=False)
if v != "lib":
    raise RuntimeError()

v = p.get_str(get_addr(11), len(gettysburg), nul_terminated=False)
if v != gettysburg:
    raise RuntimeError()

v = p.get_str(0, 0)
if v != "":
    raise RuntimeError()
v = p.get_str(0, 0, nul_terminated=False)
if v != "":
    raise RuntimeError()


# === Integer Reading Tests ===

# Check some entries in the ROM's sine table.
v = p.get_int(0xe000, 2)
if v != 0:
    raise RuntimeError()
v = p.get_int(0xe800, 2)
if v != 46340:
    raise RuntimeError()
v = p.get_ints(0xe000, 2, 10)
if v != [0, 50, 101, 151, 201, 251, 302, 352, 402, 452]:
    raise RuntimeError()

# Getting individual integers.
v = p.get_int(get_addr(13), 1)
if v != 200:
    raise RuntimeError()
v = p.get_int(get_addr(14), 1, signed=True)
if v != -120:
    raise RuntimeError()
v = p.get_int(get_addr(15), 2)
if v != 50000:
    raise RuntimeError()
v = p.get_int(get_addr(16), 2, signed=True)
if v != -20500:
    raise RuntimeError()
v = p.get_int(get_addr(17), 4)
if v != 3000000000:
    raise RuntimeError()
v = p.get_int(get_addr(18), 4, signed=True)
if v != -2000000000:
    raise RuntimeError()
v = p.get_int(get_addr(19), 2)
if v != 0xaabb:
    raise RuntimeError()
v = p.get_int(get_addr(19), 2, byteorder='big')
if v != 0xbbaa:
    raise RuntimeError()
v = p.get_int(get_addr(20), 4)
if v != 0xa0b0c0d0:
    raise RuntimeError()
v = p.get_int(get_addr(20), 4, byteorder='big')
if v != 0xd0c0b0a0:
    raise RuntimeError()

# Getting integer lists.
v = p.get_ints(get_addr(13), 1, 5)
if v != [200, 255, 0, 128, 1]:
    raise RuntimeError()
v = p.get_ints(get_addr(14), 1, 5, signed=True)
if v != [-120, 127, 0, -128, -1]:
    raise RuntimeError()
v = p.get_ints(get_addr(15), 2, 5)
if v != [50000, 65535, 0, 32768, 1]:
    raise RuntimeError()
v = p.get_ints(get_addr(16), 2, 5, signed=True)
if v != [-20500, 32767, 0, -32768, -1]:
    raise RuntimeError()
v = p.get_ints(get_addr(17), 4, 5)
if v != [3000000000, 4294967295, 0, 2147483648, 1]:
    raise RuntimeError()
v = p.get_ints(get_addr(18), 4, 5, signed=True)
if v != [-2000000000, 2147483647, 0, -2147483648, -1]:
    raise RuntimeError()
v = p.get_ints(get_addr(19), 2, 5)
if v != [0xaabb, 0xccdd, 0xeeff, 0x0011, 0x2233]:
    raise RuntimeError()
v = p.get_ints(get_addr(19), 2, 5, byteorder='big')
if v != [0xbbaa, 0xddcc, 0xffee, 0x1100, 0x3322]:
    raise RuntimeError()
v = p.get_ints(get_addr(20), 4, 5)
if v != [0xa0b0c0d0, 0xe0f00010, 0x20304050, 0x60708090, 0x0a0b0c0d]:
    raise RuntimeError()
v = p.get_ints(get_addr(20), 4, 5, byteorder='big')
if v != [0xd0c0b0a0, 0x1000f0e0, 0x50403020, 0x90807060, 0x0d0c0b0a]:
    raise RuntimeError()

# Some alignment tests.

try:
    v = p.get_int(1, 2)
    raise RuntimeError()
except ValueError:
    pass

try:
    v = p.get_ints(get_addr(19) + 1, 2, 4)
    raise RuntimeError()
except ValueError:
    pass
v = p.get_ints(get_addr(19) + 1, 2, 4, alignment='byte')
if v != [0xddaa, 0xffcc, 0x11ee, 0x3300]:
    raise RuntimeError()

try:
    v = p.get_int(get_addr(20) + 1, 4)
    raise RuntimeError()
except ValueError:
    pass
v = p.get_int(get_addr(20) + 1, 4, alignment='byte')
if v != 0x10a0b0c0:
    raise RuntimeError()

try:
    v = p.get_ints(get_addr(19) + 2, 4, 2)
    raise RuntimeError()
except ValueError:
    pass
v = p.get_ints(get_addr(19) + 2, 4, 2, alignment='word')
if v != [0xeeffccdd, 0x22330011]:
    raise RuntimeError()

# Empty list request.
v = p.get_ints(0, 4, 0)
if v != []:
    raise RuntimeError()


# === Baudrate Tests ===

v = p.get_int(0, 4)
if v != REF_CLKFREQ:
    print("WARNING: REF_CLKFREQ (" + str(REF_CLKFREQ) + ") does not have the same value as the first long of hub memory (" + str(v) + "). This will probably cause problems.")

# Use estimated clkfreq.
# This effectively tests estimate_clkfreq.
p.switch_baudrate(LOWER_BAUD)
verify_table_str(11, gettysburg)

# Use Spin's clkfreq (LONG[0]).
p.switch_baudrate(INIT_BAUD, use_hub_clkfreq=True)
verify_table_str(11, gettysburg)

# Use explicit clkfreq.
p.switch_baudrate(LOWER_BAUD, clkfreq=REF_CLKFREQ)
verify_table_str(11, gettysburg)

# Baudrate reversion -- this sends a break condition.
p.switch_baudrate(INIT_BAUD)
p.revert_baudrate()
if p.baudrate != LOWER_BAUD:
    raise RuntimeError()
verify_table_str(11, gettysburg)

p.switch_baudrate(INIT_BAUD, clkfreq=REF_CLKFREQ)
verify_table_str(11, gettysburg)


# === Fill Tests ===

# The buffer is 4000 bytes starting at a long-aligned address.
buff_addr = get_addr(21)
buff_size = 4000

try:
    p.fill_bytes(buff_addr, buff_size, b'')
    raise RuntimeError()
except ValueError:
    pass

p.fill_bytes(buff_addr, buff_size, b'\x00')
v = p.get_bytes(buff_addr, buff_size)
if v != bytearray(buff_size):
    raise RuntimeError()

p.fill_bytes(buff_addr, 0, b'cat')
v = p.get_str(buff_addr, buff_size)
if v != "":
    raise RuntimeError()

p.fill_bytes(buff_addr, 2, b'cat')
v = p.get_str(buff_addr, buff_size)
if v != "ca":
    raise RuntimeError()

p.fill_bytes(buff_addr, 3, b'cat')
v = p.get_str(buff_addr, buff_size)
if v != "cat":
    raise RuntimeError()

p.fill_bytes(buff_addr, 10, b'cat')
v = p.get_str(buff_addr, buff_size) 
if v != "catcatcatc":
    raise RuntimeError()

p.fill_bytes(buff_addr, buff_size, b'\x55')
v = p.get_bytes(buff_addr, buff_size)
for x in v:
    if x != 0x55:
        raise RuntimeError()


# === String Writing Tests ===

# At this point the buffer is known to be filled with 0x55 bytes.

# This call should write nothing to the buffer.
p.set_str(buff_addr, buff_size, "", nul_terminated=False)
v = p.get_bytes(buff_addr, 2)
if v != b'\x55\x55':
    raise RuntimeError()

# This call should write just one NUL to the buffer.
p.set_str(buff_addr, buff_size, "")
v = p.get_str(buff_addr, buff_size)
if v != "":
    raise RuntimeError()
v = p.get_bytes(buff_addr, 2)
if v != b'\x00\x55':
    raise RuntimeError()

def test_set_str(string):
    p.set_str(buff_addr, buff_size, string)
    v = p.get_str(buff_addr, buff_size)
    if v != string:
        raise RuntimeError()

test_set_str("a")
test_set_str("hi")
test_set_str("cat")
test_set_str("plop")
test_set_str("tulip")
test_set_str("cheese")
test_set_str("library")
test_set_str("elephant")
test_set_str("processor")
test_set_str(gettysburg)

p.set_str(buff_addr, buff_size, "library")
p.set_str(buff_addr, buff_size, "cat", nul_terminated=False)
v = p.get_str(buff_addr, buff_size)
if v != "catrary":
    raise RuntimeError()

# This helper clears NULs that may complicate some tests.
def write_dashes():
    filler_str = "-------------------"
    p.set_str(buff_addr, buff_size, filler_str)
    v = p.get_str(buff_addr, buff_size)
    if v != filler_str:
        raise RuntimeError()

# Attempt to write "a" in one byte with NUL termination -- requires truncation.
write_dashes()
try:
    p.set_str(buff_addr, 1, "a")
    raise RuntimeError()
except ValueError:
    pass
p.set_str(buff_addr, 1, "a", truncate=True)
v = p.get_str(buff_addr, buff_size)
if v != "":
    raise RuntimeError()

# Write "b" in one byte without NUL termination.
write_dashes()
p.set_str(buff_addr, 1, "b", nul_terminated=False)
v = p.get_str(buff_addr, 1, nul_terminated=False)
if v != "b":
    raise RuntimeError()

# Attempt to write "cat" in three bytes with NUL termination -- requires truncation.
write_dashes()
try:
    p.set_str(buff_addr, 3, "cat")
    raise RuntimeError()
except ValueError:
    pass
p.set_str(buff_addr, 3, "cat", truncate=True)
v = p.get_str(buff_addr, buff_size)
if v != "ca":
    raise RuntimeError()

# Write "cat" with NUL terminator in exactly four bytes.
write_dashes()
p.set_str(buff_addr, 4, "cat")
v = p.get_str(buff_addr, buff_size)
if v != "cat":
    raise RuntimeError()

# Attempt to write "dog" in two bytes without NUL termination.
write_dashes()
try:
    p.set_str(buff_addr, 2, "dog", nul_terminated=False)
    raise RuntimeError()
except ValueError:
    pass
p.set_str(buff_addr, 2, "dog", truncate=True, nul_terminated=False)
v = p.get_str(buff_addr, 3, nul_terminated=False)
if v != "do-":
    raise RuntimeError()

# UTF-8 test.
write_dashes()
p.set_str(buff_addr+1, buff_size, "Ⓑ", encoding="utf_8")
v = p.get_str(buff_addr+1, buff_size, encoding="utf_8")
if v != "Ⓑ":
    raise RuntimeError()


# === Integer Writing Tests ===

p.set_int(buff_addr, 1, 255)
p.set_int(buff_addr+1, 1, 128)
p.set_int(buff_addr+2, 1, 0)
v = p.get_ints(buff_addr, 1, 3)
if v != [255, 128, 0]:
    raise RuntimeError()

p.set_int(buff_addr+1, 1, -1, signed=True)
p.set_int(buff_addr+2, 1, -128, signed=True)
p.set_int(buff_addr+3, 1, 127, signed=True)
v = p.get_ints(buff_addr+1, 1, 3, signed=True)
if v != [-1, -128, 127]:
    raise RuntimeError()

p.set_int(buff_addr, 2, 0xffff)
p.set_int(buff_addr+2, 2, 0x8000)
p.set_int(buff_addr+4, 2, 0)
v = p.get_ints(buff_addr, 2, 3)
if v != [65535, 32768, 0]:
    raise RuntimeError()

try:
    p.set_int(buff_addr+1, 2, -1, signed=True)
    raise RuntimeError()
except ValueError:
    pass
p.set_int(buff_addr+1, 2, -1, signed=True, alignment='byte')
p.set_int(buff_addr+3, 2, -32768, signed=True, alignment='byte')
p.set_int(buff_addr+5, 2, 32767, signed=True, alignment='byte')
v = p.get_ints(buff_addr+1, 2, 3, signed=True, alignment='byte')
if v != [-1, -32768, 32767]:
    raise RuntimeError()

p.set_int(buff_addr, 2, 0xabcd, byteorder='big')
v = p.get_int(buff_addr, 2, byteorder='big')
if v != 0xabcd:
    raise RuntimeError()
v = p.get_int(buff_addr, 2)
if v != 0xcdab:
    raise RuntimeError()

p.set_int(buff_addr, 4, 0xffffffff)
p.set_int(buff_addr+4, 4, 0x80000000)
p.set_int(buff_addr+8, 4, 1)
v = p.get_ints(buff_addr, 4, 3)
if v != [4294967295, 2147483648, 1]:
    raise RuntimeError()

p.set_int(buff_addr, 4, -1, signed=True)
p.set_int(buff_addr+4, 4, 2147483647, signed=True)
p.set_int(buff_addr+8, 4, -2147483648, signed=True)
v = p.get_ints(buff_addr, 4, 3, signed=True)
if v != [-1, 2147483647, -2147483648]:
    raise RuntimeError()

try:
    p.set_int(buff_addr+1, 4, 0xaabbccdd)
    raise RuntimeError()
except ValueError:
    pass
p.set_int(buff_addr+1, 4, 0xaabbccdd, alignment='byte')
v = p.get_int(buff_addr+1, 4, alignment='byte')
if v != 0xaabbccdd:
    raise RuntimeError()

try:
    p.set_int(buff_addr+2, 4, 0x11223344)
    raise RuntimeError()
except ValueError:
    pass
p.set_int(buff_addr+2, 4, 0x11223344, alignment='word')
v = p.get_int(buff_addr+2, 4, alignment='word')
if v != 0x11223344:
    raise RuntimeError()

p.set_int(buff_addr, 4, 0x24681357, byteorder='big')
v = p.get_int(buff_addr, 4, byteorder='big')
if v != 0x24681357:
    raise RuntimeError()
v = p.get_int(buff_addr, 4)
if v != 0x57136824:
    raise RuntimeError()

u = [0, 127, 128, 255]
p.set_ints(buff_addr, 1, u)
v = p.get_ints(buff_addr, 1, len(u))
if v != u:
    raise RuntimeError()

u = [1, -1, 0, 127, -128]
p.set_ints(buff_addr, 1, u, signed=True)
v = p.get_ints(buff_addr, 1, len(u), signed=True)
if v != u:
    raise RuntimeError()

u = [0, 32768, 45000, 65535]
p.set_ints(buff_addr, 2, u)
v = p.get_ints(buff_addr, 2, len(u))
if v != u:
    raise RuntimeError()

u = [-1, -32768, 32767, 0, 1]
try:
    p.set_ints(buff_addr+1, 2, u, signed=True)
    raise RuntimeError()
except ValueError:
    pass
p.set_ints(buff_addr+1, 2, u, signed=True, alignment='byte')
v = p.get_ints(buff_addr+1, 2, len(u), signed=True, alignment='byte')
if v != u:
    raise RuntimeError()

u = [4294967295, 2147483648, 1, 0]
p.set_ints(buff_addr, 4, u)
v = p.get_ints(buff_addr, 4, len(u))
if v != u:
    raise RuntimeError()

u = [-2147483648, 2147483647, -1, 1, 0]
p.set_ints(buff_addr, 4, u, signed=True)
v = p.get_ints(buff_addr, 4, len(u), signed=True)
if v != u:
    raise RuntimeError()

u = [3000000000, 40, 27000000, 2]
try:
    p.set_ints(buff_addr+1, 4, u)
    raise RuntimeError()
except ValueError:
    pass
p.set_ints(buff_addr+1, 4, u, alignment='byte')
v = p.get_ints(buff_addr+1, 4, len(u), alignment='byte')
if v != u:
    raise RuntimeError()

u = [-2000000000, 1000, 2000000000, 2]
try:
    p.set_ints(buff_addr+2, 4, u, signed=True)
    raise RuntimeError()
except ValueError:
    pass
try:
    p.set_ints(buff_addr+3, 4, u, signed=True, alignment='word')
    raise RuntimeError()
except ValueError:
    pass
p.set_ints(buff_addr+2, 4, u, signed=True, alignment='word')
v = p.get_ints(buff_addr+2, 4, len(u), signed=True, alignment='word')
if v != u:
    raise RuntimeError()

def fill_area(size, byte):
    u = bytearray(size)
    for i in range(0, size):
        u[i] = byte
    p.fill_bytes(buff_addr, size, byte.to_bytes(1, 'little'))
    v = p.get_bytes(buff_addr, size)
    if v != u:
        raise RuntimeError()
    return u

u = fill_area(10, 0x55)
u[0] = 0x15
p.set_int(buff_addr, 1, 0x15)
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0xaa)
u[0] = 0x90
u[1] = 0x40
p.set_int(buff_addr, 2, 0x4090)
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0x55)
u[3] = 0x10
u[4] = 0x20
u[5] = 0x30
u[6] = 0x40
p.set_int(buff_addr+3, 4, 0x40302010, alignment='byte')
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0xaa)
u[0] = 230
p.set_ints(buff_addr, 1, [230])
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0x55)
u[1] = 0xcc
u[2] = 0xdd
p.set_ints(buff_addr+1, 2, [0xccdd], byteorder='big', alignment='byte')
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0xaa)
u[2] = 0x40
u[3] = 0x30
u[4] = 0x20
u[5] = 0x10
p.set_ints(buff_addr+2, 4, [0x10203040], alignment='word')
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()

u = fill_area(10, 0x55)
p.set_ints(buff_addr, 1, [])
p.set_ints(buff_addr+2, 2, [])
p.set_ints(buff_addr+4, 4, [])
v = p.get_bytes(buff_addr, 10)
if v != u:
    raise RuntimeError()


# === Binary Data Tests ===

def random_bytes(size):
    u = bytearray(size)
    for i in range(0, size):
        u[i] = random.randint(0, 255)
    return u

u = bytearray(buff_size)
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, buff_size)
if v != u:
    raise RuntimeError()

p.set_bytes(buff_addr, b'\xab')
p.set_bytes(buff_addr+1, b'\xcd\xef\x01\x23')
p.set_bytes(buff_addr, b'')
v = p.get_bytes(buff_addr, 10)
if v != b'\xab\xcd\xef\x01\x23\x00\x00\x00\x00\x00':
    raise RuntimeError()

r = random_bytes(100)
u = bytearray(50) + r + bytearray(50)
p.set_bytes(buff_addr+200, r)
v = p.get_bytes(buff_addr+150, 200)
if v != u:
    raise RuntimeError()

u = random_bytes(PeekPoke.MAX_ATOMIC_WRITE)
p.set_bytes(buff_addr, u, atomic=True)
v = p.get_bytes(buff_addr, len(u), atomic=True)
if v != u:
    raise RuntimeError()

u = random_bytes(PeekPoke.MAX_ATOMIC_WRITE+1)
try:
    p.set_bytes(buff_addr, u, atomic=True)
    raise RuntimeError()
except ValueError:
    # expected since the size exceeds the max atomic write limit
    pass
p.set_bytes(buff_addr, u)
# The max atomic read is greater than the max write.
v = p.get_bytes(buff_addr, len(u), atomic=True)
if v != u:
    raise RuntimeError()

u = random_bytes(PeekPoke.MAX_ATOMIC_READ)
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, len(u), atomic=True)
if v != u:
    raise RuntimeError()

u = random_bytes(PeekPoke.MAX_ATOMIC_READ+1)
p.set_bytes(buff_addr, u)
try:
    v = p.get_bytes(buff_addr, len(u), atomic=True)
    raise RuntimeError()
except ValueError:
    # expected since the size exceeds the max atomic read limit
    pass
v = p.get_bytes(buff_addr, len(u))
if v != u:
    raise RuntimeError()

h = buff_size // 2
r = random_bytes(h)
u = r + bytearray(buff_size - h)
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, buff_size)
if v != u:
    raise RuntimeError()

r2 = random_bytes(buff_size - h)
u = r + r2
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, buff_size)
if v != u:
    raise RuntimeError()


# === All Done ===

end_time = time.perf_counter()

print(" Testing actually took {0:#.1f} seconds.".format(end_time-start_time))
print(" ALL TESTS PASSED")

