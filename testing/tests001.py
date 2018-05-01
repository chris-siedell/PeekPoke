# tests001.py
# 1 May 2018
# Chris Siedell
# source: https://github.com/chris-siedell/PeekPoke
# python: https://pypi.org/project/peekpoke/
# homepage: http://siedell.com/projects/PeekPoke/


# Warning: the break condition will be sent during this test. This may
#  affect other devices on the serial line.


import sys
import time
import datetime
import random
from peekpoke import PeekPoke
from peekpoke import PeekPokeInfo
from peekpoke import RestrictedAddressError
from crow.admin import CrowAdmin
from crow.errors import NoResponseError
from crow.errors import PortNotOpenError
from crow.errors import InvalidCommandError
from crow.errors import CommandNotAvailableError


if len(sys.argv) < 2:
    sys.exit("Please provide the serial port name as a command line argument.")

serial_port_name = sys.argv[1]


# These constants come from the PeekPoke.spin and setup001.spin.
REF_CLKFREQ = 80000000
HIGHER_BAUD = 115200
LOWER_BAUD = 57600
PAYLOAD_BUFF = 4*56
BUFF_SIZE = 1480
MIN_VERSION = 1525211100


def str_from_version(version):
    return datetime.datetime.utcfromtimestamp(version).strftime('%Y-%m-%d %H:%M:%S') + " UTC"


print("PeekPoke Tests 001, 1 May 2018")
print(" Serial port: " + serial_port_name)
print(" Assumptions:")
print("  - it is safe to send a break condition,")
print("  - setup001.spin is running,")
print("  - setup001's version is at least " + str(MIN_VERSION) + " (" + str_from_version(MIN_VERSION) + "),")
print("  - the reference values have not been overwritten,")
print("  - the Propeller and the PC can communicate at " + str(HIGHER_BAUD) + " and " + str(LOWER_BAUD) + " bps,")
print("  - the Propeller's clock frequency is " + str(REF_CLKFREQ) + " Hz.")
print(" If a previous test failed it may be necessary to reboot the Propeller.")
print(" These tests do not overwrite the reference values.")
print(" Testing should take about 0000 seconds.")
print(" ...")

start_time = time.perf_counter()

p = PeekPoke(serial_port_name)


# === Service Check ===

# Verify that a Crow device exists at the given serial port and address,
#  and that it is running a PeekPoke service on the expected Crow port.
admin = CrowAdmin(serial_port_name, default_address=p.address)
admin.ping()
port_info = admin.get_port_info(p.port)
if not port_info['is_open']:
    raise RuntimeError("The PeekPoke service port is closed.")
if 'service_identifier' in port_info:
    if port_info['service_identifier'] != "PeekPoke":
        raise RuntimeError("There is an unexpected service at the PeekPoke port (" + port_info['service_identifier'] + ").")
else:
    raise RuntimeError("The service at the PeekPoke port unexpectedly does not have an identifier.")


# === Miscellaneous Methods Tests, Part 1 ===

# par points to the address table, which holds the addresses to various
#  reference items in hub memory.
addrTableAddr = p.get_par()

# get_addr obtains the address of the given item in the address table.
def get_addr(index):
    return p.get_int(addrTableAddr + 2*index, 2)


# === Verify Min Version of setup001.spin is Running ===

v = p.get_str(get_addr(0), 20)
if v != "setup001":
    raise RuntimeError("This test requires that the Propeller be running setup001.spin.")

v = p.get_int(get_addr(23), 4)
if v < MIN_VERSION:
    raise RuntimeError("The Propeller is running an old version of setup001.spin. This test requires a version of " + str(MIN_VERSION) + " (" + str_from_version(MIN_VERSION) + ") or later, but the Propeller is running version " + str(v) + " (" + str_from_version(v) + ").") 


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
    # expect ValueError since five bytes provided
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


# === Miscellaneous Methods Tests, Part 2  ===

est_clkfreq = p.estimate_clkfreq()

# This call should result in using a cached value (no command sent to Propeller).
v = p.get_identifier()
if v != 0:
    raise RuntimeError()

# This call should result in using a cached value (no command sent to Propeller).
par2 = p.get_par()
if addrTableAddr != par2:
    raise RuntimeError()

ref_info1 = PeekPokeInfo()
ref_info1.min_read_address = 0
ref_info1.max_read_address = 0xffff
ref_info1.min_write_address = 0
ref_info1.max_write_address = 0xffff
ref_info1.identifier = 0
ref_info1.par = addrTableAddr
ref_info1.available_commands_bitmask = 0x80ff

def verify_and_print_info(info, ref_info, address):
    if info.max_atomic_read != PAYLOAD_BUFF - 4:
        raise RuntimeError("PAYLOAD_BUFF may need to be updated. It should be equal to cMaxPayloadSize in PeekPoke.spin.")
    if info.max_atomic_write != PAYLOAD_BUFF - 8:
        raise RuntimeError("PAYLOAD_BUFF may need to be updated. It should be equal to cMaxPayloadSize in PeekPoke.spin.")
    if info.min_read_address != ref_info.min_read_address:
        raise RuntimeError()
    if info.max_read_address != ref_info.max_read_address:
        raise RuntimeError()
    if info.min_write_address != ref_info.min_write_address:
        raise RuntimeError()
    if info.max_write_address != ref_info.max_write_address:
        raise RuntimeError()
    if info.identifier != ref_info.identifier:
        raise RuntimeError()
    if info.par != ref_info.par:
        raise RuntimeError()
    if info.available_commands_bitmask != ref_info.available_commands_bitmask:
        raise RuntimeError()
    if info.serial_timings_format != 0:
        raise RuntimeError()
    if info.peekpoke_version != 2:
        raise RuntimeError()
    print(" Info for instance at address " + str(address) + ":")
    print(" " + str(info))
    print(" ...")

# After this call there should be two getInfo commands visible using a logic analyzer (command payload
#  is 0x70, 0x70, 0x00, 0x00) --  one for the first get_par call, and one for this get_info call.
info1 = p.get_info(use_cached=False)
verify_and_print_info(info1, ref_info1, 1)


# === String Reading Tests ===

# Check the copyright message in the ROM.
v = p.get_str(65297, 30)
if v != "Copyright 2005  Parallax, Inc.":
    raise RuntimeError()

# Items at indices 1 to 12 in the address table are NUL-terminated strings.

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

hub_clkfreq = p.get_int(0, 4)
if hub_clkfreq != REF_CLKFREQ:
    print("WARNING: REF_CLKFREQ (" + str(REF_CLKFREQ) + ") does not have the same value as the first long of hub memory (" + str(v) + "). This will probably cause problems.")

# Use estimated clkfreq.
# This effectively tests estimate_clkfreq.
p.switch_baudrate(LOWER_BAUD)
verify_table_str(11, gettysburg)

# Use Spin's clkfreq (LONG[0]).
p.switch_baudrate(HIGHER_BAUD, use_hub_clkfreq=True)
verify_table_str(11, gettysburg)

# Use explicit clkfreq.
p.switch_baudrate(LOWER_BAUD, clkfreq=REF_CLKFREQ)
verify_table_str(11, gettysburg)

# Baudrate reversion -- this sends a break condition.
p.switch_baudrate(HIGHER_BAUD)
p.revert_baudrate()
if p.baudrate != LOWER_BAUD:
    raise RuntimeError()
verify_table_str(11, gettysburg)

p.switch_baudrate(HIGHER_BAUD, clkfreq=REF_CLKFREQ)
verify_table_str(11, gettysburg)


# === Fill Tests ===

# The buffer is 4000 bytes starting at a long-aligned address.
buff_addr = get_addr(21)

try:
    p.fill_bytes(buff_addr, BUFF_SIZE, b'')
    raise RuntimeError()
except ValueError:
    pass

p.fill_bytes(buff_addr, BUFF_SIZE, b'\x00')
v = p.get_bytes(buff_addr, BUFF_SIZE)
if v != bytearray(BUFF_SIZE):
    raise RuntimeError()

p.fill_bytes(buff_addr, 0, b'cat')
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "":
    raise RuntimeError()

p.fill_bytes(buff_addr, 2, b'cat')
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "ca":
    raise RuntimeError()

p.fill_bytes(buff_addr, 3, b'cat')
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "cat":
    raise RuntimeError()

p.fill_bytes(buff_addr, 10, b'cat')
v = p.get_str(buff_addr, BUFF_SIZE) 
if v != "catcatcatc":
    raise RuntimeError()

p.fill_bytes(buff_addr, BUFF_SIZE, b'\x55')
v = p.get_bytes(buff_addr, BUFF_SIZE)
for x in v:
    if x != 0x55:
        raise RuntimeError()


# === String Writing Tests ===

# At this point the buffer is known to be filled with 0x55 bytes.

# This call should write nothing to the buffer.
p.set_str(buff_addr, BUFF_SIZE, "", nul_terminated=False)
v = p.get_bytes(buff_addr, 2)
if v != b'\x55\x55':
    raise RuntimeError()

# This call should write just one NUL to the buffer.
p.set_str(buff_addr, BUFF_SIZE, "")
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "":
    raise RuntimeError()
v = p.get_bytes(buff_addr, 2)
if v != b'\x00\x55':
    raise RuntimeError()

def test_set_str(string):
    p.set_str(buff_addr, BUFF_SIZE, string)
    v = p.get_str(buff_addr, BUFF_SIZE)
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

p.set_str(buff_addr, BUFF_SIZE, "library")
p.set_str(buff_addr, BUFF_SIZE, "cat", nul_terminated=False)
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "catrary":
    raise RuntimeError()

# This helper clears NULs that may complicate some tests.
def write_dashes():
    filler_str = "-------------------"
    p.set_str(buff_addr, BUFF_SIZE, filler_str)
    v = p.get_str(buff_addr, BUFF_SIZE)
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
v = p.get_str(buff_addr, BUFF_SIZE)
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
v = p.get_str(buff_addr, BUFF_SIZE)
if v != "ca":
    raise RuntimeError()

# Write "cat" with NUL terminator in exactly four bytes.
write_dashes()
p.set_str(buff_addr, 4, "cat")
v = p.get_str(buff_addr, BUFF_SIZE)
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
p.set_str(buff_addr+1, BUFF_SIZE, "Ⓑ", encoding="utf_8")
v = p.get_str(buff_addr+1, BUFF_SIZE, encoding="utf_8")
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

# Write and read the entire reserved buffer. The timings
#  will be used to display throughput at the end.
u = bytearray(BUFF_SIZE)
write_start = time.perf_counter()
p.set_bytes(buff_addr, u)
read_start = write_end = time.perf_counter()
v = p.get_bytes(buff_addr, BUFF_SIZE)
read_end = time.perf_counter()
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

u = random_bytes(info1.max_atomic_write)
p.set_bytes(buff_addr, u, atomic=True)
v = p.get_bytes(buff_addr, len(u), atomic=True)
if v != u:
    raise RuntimeError()

u = random_bytes(info1.max_atomic_write+1)
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

u = random_bytes(info1.max_atomic_read)
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, len(u), atomic=True)
if v != u:
    raise RuntimeError()

u = random_bytes(info1.max_atomic_read+1)
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

h = BUFF_SIZE // 2
r = random_bytes(h)
u = r + bytearray(BUFF_SIZE - h)
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, BUFF_SIZE)
if v != u:
    raise RuntimeError()

r2 = random_bytes(BUFF_SIZE - h)
u = r + r2
p.set_bytes(buff_addr, u)
v = p.get_bytes(buff_addr, BUFF_SIZE)
if v != u:
    raise RuntimeError()


# === get_info Tests for All Remaining Instances ===

# These should work even though the use_cached argument defaults
#  to True. Every time the address or port changes the cached value
#  should be invalidated.

ref_info2 = PeekPokeInfo()
ref_info2.min_read_address = buff_addr
ref_info2.max_read_address = buff_addr + BUFF_SIZE - 1
ref_info2.min_write_address = buff_addr
ref_info2.max_write_address = buff_addr + BUFF_SIZE//2 - 1
ref_info2.identifier = 1
ref_info2.par = buff_addr
ref_info2.available_commands_bitmask = 0x80ff

p.address = 2
info2 = p.get_info()
verify_and_print_info(info2, ref_info2, 2)

ref_info3 = PeekPokeInfo()
ref_info3.min_read_address = buff_addr
ref_info3.max_read_address = buff_addr
ref_info3.min_write_address = buff_addr+1
ref_info3.max_write_address = buff_addr+1
ref_info3.identifier = 0xffffffff
ref_info3.par = buff_addr
ref_info3.available_commands_bitmask = 0x80ff

p.address = 3
info3 = p.get_info()
verify_and_print_info(info3, ref_info3, 3)

ref_info4 = PeekPokeInfo()
ref_info4.min_read_address = 0x0000
ref_info4.max_read_address = 0xffff
ref_info4.min_write_address = 0x0000
ref_info4.max_write_address = 0xffff
ref_info4.identifier = 0x7fffffff
ref_info4.par = 0
ref_info4.available_commands_bitmask = 0x00ff

p.address = 4
try:
    info4 = p.get_info()
    raise RuntimeError()
except NoResponseError:
    # expected since address 4 is using LOWER_BAUD
    pass
p.baudrate = LOWER_BAUD
try:
    info4 = p.get_info()
    raise RuntimeError()
except PortNotOpenError:
    # expected since port 200 was selected
    pass
p.port = 200
info4 = p.get_info()
verify_and_print_info(info4, ref_info4, 4)

# Try creating another instance using optional arguments.
p5 = PeekPoke(serial_port_name, address=5, port=255)

ref_info5 = PeekPokeInfo()
ref_info5.min_read_address = 0x0000
ref_info5.max_read_address = 0xffff
ref_info5.min_write_address = 0x0000
ref_info5.max_write_address = 0xffff
ref_info5.identifier = 0
ref_info5.par = 2016
ref_info5.available_commands_bitmask = 0x00db

info5 = p5.get_info()
verify_and_print_info(info5, ref_info5, 5)

p6 = PeekPoke(serial_port_name, address=6)

ref_info6 = PeekPokeInfo()
ref_info6.min_read_address = 0x0000
ref_info6.max_read_address = 0xffff
ref_info6.min_write_address = 0x0000
ref_info6.max_write_address = 0xffff
ref_info6.identifier = 0xaabbccdd
ref_info6.par = 0xfffc
ref_info6.available_commands_bitmask = 0x80ff

info6 = p6.get_info()
verify_and_print_info(info6, ref_info6, 6)

ref_info7 = PeekPokeInfo()
ref_info7.min_read_address = 1
ref_info7.max_read_address = 0x7fff
ref_info7.min_write_address = 0x0000
ref_info7.max_write_address = 0xffff
ref_info7.identifier = 2018
ref_info7.par = 0x8000
ref_info7.available_commands_bitmask = 0x81ff

p.address = 7
p.port = 112
info7 = p.get_info()
verify_and_print_info(info7, ref_info7, 7)

ref_info8 = PeekPokeInfo()
ref_info8.min_read_address = 1
ref_info8.max_read_address = 0x7fff
ref_info8.min_write_address = 0x0000
ref_info8.max_write_address = 0xffff
ref_info8.identifier = 2018
ref_info8.par = get_addr(22)
ref_info8.available_commands_bitmask = 0x80ff

p.address = 8
info8 = p.get_info()
verify_and_print_info(info8, ref_info8, 8)


# === Verify Restricted Memory Op Ranges ===

# todo


# === Verify No Wrap Around ===

# Memory operations are not allowed to wrap aroung the end of the hub
#  address space. This is enforced locally and remotely.
p.address = 1
v = p.get_int(65535, 1)
if v != 1:
    raise RuntimeError()
v = p.get_int(65532, 4)
if v != 24248068:
    raise RuntimeError()
# Effectively same as above but bypassing local checks -- this should work.
t = p._host.send_command(address=p.address, port=p.port, payload=b'\x70\x70\x00\x01\xfc\xff\x04\x00')
v = int.from_bytes(t.response[4:8], 'little')
if v != 24248068:
    raise RuntimeError()
try:
    v = p.get_int(65533, 4, alignment='byte')
    raise RuntimeError()
except ValueError:
    # expected due to wrap around (local error)
    pass
try:
    # Effectively same as above (address 65533 = 0xfffd) but bypassing 
    #  local check -- this should fail.
    t = p._host.send_command(address=p.address, port=p.port, payload=b'\x70\x70\x00\x01\xfd\xff\x04\x00')
    raise RuntimeError()
except InvalidCommandError:
    # expected due to wrap around (remote error)
    pass

# This is effectively get_str(65535, 2), which should fail (bypasses local checks).
try:
    t = p._host.send_command(address=p.address, port=p.port, payload=b'\x70\x70\x00\x03\xff\xff\x02\x00')
    raise RuntimeError()
except InvalidCommandError:
    # expected due to wrap around (remote error)
    pass

# This is effectively set_bytes(65535, 2), which should fail (bypasses local checks).
try:
    t = p._host.send_command(address=p.address, port=p.port, payload=b'\x70\x70\x00\x02\xff\xff\x02\x00\xaa\xbb')
    raise RuntimeError()
except InvalidCommandError:
    # expected due to wrap around (remote error)
    pass

# Fundamentally, there are just three PeekPoke protocol hub memory operations (readHub, writeHub, and
#  readHubStr), so the above exhausts the possibilities. In fact, all three ops share the same wrap
#  around checking code.

# All the local memory ops should use the same underlying method to enforce no wrapping (_verify_hub_args),
#  so the following is just to verify that it is always being called.
# Memory ops: get_bytes, set_bytes, fill_bytes, get_str, set_str, get_int, set_int, get_ints, set_ints.
# todo: automate this visual inspection check
print(" Nine error messages regarding wrap around should follow.")
try:
    p.get_bytes(65535, 2)
    raise RuntimeError()
except ValueError as e:
    print(" 1. " + str(e))
try:
    p.set_bytes(65535, b'hi')
    raise RuntimeError()
except ValueError as e:
    print(" 2. " + str(e))
try:
    p.fill_bytes(65535, 2, b'cat')
    raise RuntimeError()
except ValueError as e:
    print(" 3. " + str(e))
try:
    p.get_str(65535, 2)
    raise RuntimeError()
except ValueError as e:
    print(" 4. " + str(e))
try:
    p.set_str(65535, 2, "a")
    raise RuntimeError()
except ValueError as e:
    print(" 5. " + str(e))
try:
    p.get_int(65535, 2, alignment='byte')
    raise RuntimeError()
except ValueError as e:
    print(" 6. " + str(e))
try:
    p.set_int(65535, 2, 0xffff, alignment='byte')
    raise RuntimeError()
except ValueError as e:
    print(" 7. " + str(e))
try:
    p.get_ints(65535, 1, 2)
    raise RuntimeError()
except ValueError as e:
    print(" 8. " + str(e))
try:
    p.set_ints(65535, 1, [0xff, 0xff])
    raise RuntimeError()
except ValueError as e:
    print(" 9. " + str(e))
print(" ...")


# === Verify Disabled/Enabled Break Detection ===

# The instance at address 4 can change baudrate, but it has
#  break detection disabled.
# The instance at address 6 can change baudrate, and it has
#  break detection enabled.

# Confirm that address 4 can change baudrate, and then set it
#  up for a break detection test.
p.address = 4
p.port = 200
# Confirm at lower rate.
if p.baudrate != LOWER_BAUD:
    raise RuntimeError()
v = p.get_int(0x8000, 1)
if v != 0xff:
    raise RuntimeError()
# Go to higher rate and confirm.
p.switch_baudrate(HIGHER_BAUD)
if p.baudrate != HIGHER_BAUD:
    raise RuntimeError()
v = p.get_str(65297, 30)
if v != "Copyright 2005  Parallax, Inc.":
    raise RuntimeError()
# Switch back to lower rate, but don't communicate.
p.switch_baudrate(LOWER_BAUD, clkfreq=REF_CLKFREQ)
if p.baudrate != LOWER_BAUD:
    raise RuntimeError()

# At this point the instance at address 4 has the HIGHER_BAUD
#  timings as its last good values, but since break detection
#  is disabled these values will not be used for baud reset.

# Now confirm address 6 can change baudrate (this has to be
#  done with a different local object).
if p6.baudrate != HIGHER_BAUD:
    raise RuntimeError()
# Switch to lower rate.
p6.switch_baudrate(LOWER_BAUD)
if p6.baudrate != LOWER_BAUD:
    raise RuntimeError()
v = p6.get_int(0x8000, 1)
if v != 0xff:
    raise RuntimeError()
# Switch to higher rate.
p6.switch_baudrate(HIGHER_BAUD, clkfreq=REF_CLKFREQ)
if p6.baudrate != HIGHER_BAUD:
    raise RuntimeError()
v = p6.get_int(0xffff, 1)
if v != 0x01:
    raise RuntimeError()
# Now switch to lower rate but don't communicate.
p6.switch_baudrate(LOWER_BAUD)
if p6.baudrate != LOWER_BAUD:
    raise RuntimeError()

# At this point the instance at address 6 also has HIGHER_BAUD
#  timings as its last good values, and since break detection
#  is enabled they should be applied when a break is sent.

# Using object p to send the break.
# (Currently, objects are not aware of breaks sent by other
#  objects -- this may change in the future.)
p.revert_baudrate()

# Object p should now be at the higher rate, but since the instance
#  at address 4 has break detection disabled it is still using
#  the lower rate. Therefore communications should fail.
if p.baudrate != HIGHER_BAUD:
    raise RuntimeError()
try:
    v = p.get_int(0x8000, 1)
    raise RuntimeError()
except NoResponseError:
    # expected since instance at address 4 still at lower rate
    pass
# Use lower baud and confirm that it works.
p.baudrate = LOWER_BAUD
v = p.get_int(0x8000, 1)
if v != 0xff:
    raise RuntimeError()

# Object p6 was not aware a break was sent, so the local baudrate
#  should still be the lower value.
if p6.baudrate != LOWER_BAUD:
    raise RuntimeError()
# However, the instance at address 6 should be using the higher
#  rate due to the break, so simply changing the local baudrate
#  should restore communications.
p6.baudrate = HIGHER_BAUD
v = p6.get_str(65297, 30)
if v != "Copyright 2005  Parallax, Inc.":
    raise RuntimeError()


# === Verify Disabled/Enabled Hub Writing ===

# The instance at address 5 has disabled hub writing, while the
#  instance at address 6 has enabled it.

p.address = 6
p.port = 112
p.set_bytes(buff_addr, b'U')
p.address = 5
p.port = 255
v = p.get_bytes(buff_addr, 1)
if v != b'U':
    raise RuntimeError()
try:
    p.set_bytes(buff_addr, b'V')
    raise RuntimeError()
except CommandNotAvailableError:
    # expected, since address 5 has disabled hub writes
    pass
v = p.get_bytes(buff_addr, 1)
if v != b'U':
    raise RuntimeError()


# === Verify Disabled/Enabled Baud Setting ===

# todo


# === Verify Disabled/Enabled PayloadExec ===

# All instances except the one at address 7 should have
#  payloadExec disabled.

# This code block passes the minimum size test (>= 8), but
#  since the layout_id is different from the implementation's
#  it should never be executed. If payloadExec is enabled
#  we'll get InvalidCommandError.
block = bytearray(info1.layout_id) + bytearray(4)
block[0] = block[0] ^ 1

def verify_payloadExec_disabled(address, port):
    p.address = address
    p.port = port
    try:
        p._payload_exec(block)
        raise RuntimeError()
    except CommandNotAvailableError:
        pass

# Verify the disabled instances.
verify_payloadExec_disabled(1, 112)
verify_payloadExec_disabled(2, 112)
verify_payloadExec_disabled(3, 112)
verify_payloadExec_disabled(4, 200)
verify_payloadExec_disabled(5, 255)
verify_payloadExec_disabled(6, 112)
verify_payloadExec_disabled(8, 112)

# Verify that address 7 has enabled payloadExec.
p.address = 7
p.port = 112
try:
    p._payload_exec(block)
    raise RuntimeError()
except InvalidCommandError:
    pass


# === Confirm PeekPoke.spin's new Results ===

# The return values are the new cog's ID + 1, so the
#  last value should indicate failure (all cogs in use).
p.address = 1
p.port = 112
v = p.get_ints(get_addr(22), 1, 8)
if v != [2, 3, 4, 5, 6, 7, 8, 0]:
    raise RuntimeError()


# === Serial Settings Persistence Test ===

# After a successful communication the PropCR byte ordering -- which
#  is not the default -- should 'stick', even when there is no object
#  using that address. This persistence should apply to all clients
#  using the address and port, not just the PeekPoke object.
# The same applies to the baudrate, even though not all addresses are
#  using the same baudrate.
# Using echo since it requires the correct PropCR byte ordering.
for i in range(1, 9):
    admin.echo(address=i, data=b'echo echo echo')


# === All Done ===

end_time = time.perf_counter()

read_dur = read_end - read_start
write_dur = write_end - write_start

read_rate = BUFF_SIZE / read_dur
write_rate = BUFF_SIZE / write_dur

theo_read_bytes = (HIGHER_BAUD / 10.0) * read_dur
theo_write_bytes = (HIGHER_BAUD / 10.0) * write_dur

read_pct = 100.0 * (BUFF_SIZE / theo_read_bytes)
write_pct = 100.0 * (BUFF_SIZE / theo_write_bytes)

print(" System clock frequencies...")
print("  local value (REF_CLKFREQ): " + str(REF_CLKFREQ))
print("         from hub (LONG[0]): " + str(hub_clkfreq))
print("    from estimate_clkfreq(): {:#.1f}".format(est_clkfreq))
print(" A single call to get_bytes for {0} bytes took {1:#.3f} seconds at {2} bps,".format(BUFF_SIZE, read_dur, HIGHER_BAUD))
print("  giving a reading rate of {0:#.1f} bytes per second ({1:#.1f}% of baudrate max).".format(read_rate, read_pct))
print(" A single call to set_bytes for {0} bytes took {1:#.3f} seconds at {2} bps,".format(BUFF_SIZE, write_dur, HIGHER_BAUD))
print("  giving a writing rate of {0:#.1f} bytes per second ({1:#.1f}% of baudrate max).".format(write_rate, write_pct))
print(" Testing actually took {0:#.1f} seconds.".format(end_time-start_time))
print(" ALL TESTS PASSED")

