# PeekPoke
# 27 April 2018
# Chris Siedell
# source: https://github.com/chris-siedell/PeekPoke
# python: https://pypi.org/project/peekpoke/
# homepage: http://siedell.com/projects/PeekPoke/


from crow.host import Host
from crow.host_serial import HostSerialSettings
from crow.errors import ClientError


__version__ = '0.5.0'
VERSION = __version__


class PeekPoke():

    MAX_ATOMIC_READ = 260
    MAX_ATOMIC_WRITE = 256

    def __init__(self, serial_port_name, address=1, port=112):
        if address < 1 or address > 31:
            raise ValueError("The address must be 1 to 31.")
        if port < 0 or port > 255:
            raise ValueError("The port must be 0 to 255.")
        self._address = address
        self._port = port
        self._host = Host(serial_port_name)
        self._select_propcr_order()
        self._last_good_baudrate = None
        self._break_duration = 400

    @property
    def serial_port_name(self):
        return self._host.serial_port.name

    @serial_port_name.setter
    def serial_port_name(self, serial_port_name):
        self._revert_propcr_order()
        try:
            self._host = Host(serial_port_name)
        finally:
            self._select_propcr_order()
            self._last_good_baudrate = None

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, address):
        if address < 1 or address > 31:
            raise ValueError("The address must be 1 to 31.")
        self._revert_propcr_order()
        self._address = address
        self._select_propcr_order()
        self._last_good_baudrate = None

    # The save and revert technique being used here can 'fix' the default propcr order.
    #  The underlying settings object for the address will initially have propcr_order=None,
    #  meaning that the default for the serial port should be used. If it was None when select
    #  was called, then when revert is called it will be set to whatever the default was when
    #  select was previously called.
    # I don't think this will be a problem in practice.

    def _revert_propcr_order(self):
        # Call before the host or address will change.
        self._host.serial_port.set_propcr_order(self._address, self._prev_propcr_order)

    def _select_propcr_order(self):
        # Call after the host or address has changed.
        self._prev_propcr_order = self._host.serial_port.get_propcr_order(self._address)
        self._host.serial_port.set_propcr_order(self._address, True)

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, port):
        if port < 0 or port > 255:
            raise ValueError("The port must be 0 to 255.")
        self._port = port


    # Miscellaneous

    def get_par(self):
        info = self._get_info()
        return info.par


    # Hub Memory Operations

    def get_bytearray(self, hub_address, count, *, atomic=False):
        PeekPoke._verify_hub_args(hub_address, count, True, atomic)
        result = bytearray()
        while count > 0:
            atomic_count = min(count, PeekPoke.MAX_ATOMIC_READ)
            count -= atomic_count
            result += self._read_hub(hub_address, atomic_count)
            hub_address = (hub_address + atomic_count)%65536
        return result

    def set_bytearray(self, hub_address, data, *, atomic=False):
        PeekPoke._verify_hub_args(hub_address, count, False, atomic)
        count = len(data)
        index = 0
        while count > 0:
            atomic_count = min(count, PeekPoke.MAX_ATOMIC_WRITE)
            count -= atomic_count
            self._write_hub(hub_address, data[index:index+atomic_count])
            hub_address = (hub_address + atomic_count)%65536
            index += atomic_count

    def get_str(self, hub_address, max_bytes, *, encoding='latin_1', errors='replace', nul_terminated=True, atomic=False):
        PeekPoke._verify_hub_args(hub_address, max_bytes, True, atomic)
        result = bytearray()
        if nul_terminated:
            while max_bytes > 0:
                atomic_max_bytes = min(max_bytes, PeekPoke.MAX_ATOMIC_READ)
                max_bytes -= atomic_max_bytes
                result += self._read_hub_str(hub_address, atomic_max_bytes)
                hub_address = (hub_address + atomic_max_bytes)%65536
                if result[-1] == 0:
                    break
        else:
            while max_bytes > 0:
                atomic_count = min(max_bytes, PeekPoke.MAX_ATOMIC_READ)
                max_bytes -= atomic_count
                result += self._read_hub(hub_address, atomic_count)
                hub_address = (hub_address + atomic_count)%65536
        if nul_terminated and result[-1] == 0:
            return result[0:-1].decode(encoding=encoding, errors=errors)
        else:
            return result.decode(encoding=encoding, errors=errors)

    def set_str(self, hub_address, string, max_bytes, *, encoding='latin_1', errors='replace', nul_terminated=True, atomic=False):
        data = string.encode(encoding=encoding, errors=errors)
        if nul_terminated:
            new_data = bytearray(data)
            data = new_data + b'\x00'
        if len(data) > max_bytes:
            raise ValueError("The encoded string size (" + str(len(data)) + ") exceeds the max_bytes limit (" + str(max_bytes) + ").")
        self.set_bytearray(hub_address, data, atomic=atomic)

    # todo: add stride options to int methods
    # todo: add three byte lengths to int methods

    def get_byte(self):
        pass

    def get_word(self):
        pass

    def get_long(self):
        pass

    def set_byte(self):
        pass

    def set_word(self):
        pass

    def set_long(self):
        pass

    def get_bytes(self):
        pass

    def get_words(self):
        pass

    def get_longs(self):
        pass

    def set_bytes(self):
        pass

    def set_words(self):
        pass

    def set_longs(self):
        pass

    def get_int(self, hub_address, length, *, alignment='length', byteorder='little', signed=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_hub_args(hub_address, length, True, True)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        data = self._read_hub(hub_address, length)
        return int.from_bytes(data, byteorder, signed=signed)

    def set_int(self, hub_address, integer, length, *, alignment='length', byteorder='little', signed=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_hub_args(hub_address, length, False, True)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        data = integer.to_bytes(length, byteorder, signed=signed)
        self._write_hub(hub_address, data)

    def get_ints(self, hub_address, count, length, *, byteorder='little', signed=False, atomic=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        num_bytes = count*length
        data = self.get_bytearray(hub_address, num_bytes, atomic=atomic)
        integers = []
        index = 0
        for _i in range(0, count):
            integers += int.from_bytes(data[index:index+length], byteorder, signed=signed)
        return integers

    def set_ints(self, hub_address, integers, length, *, byteorder='little', signed=False, atomic=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        data = bytearray()
        for i in integers:
            data += i.to_bytes(length, byteorder, signed=signed)
        self.set_bytearray(hub_address, data, atomic=atomic)  

    @staticmethod
    def _verify_int_length(length):
        if length != 1 and length != 2 and length != 4 and length != 8:
            raise ValueError("Valid int lengths are 1, 2, 4, and 8 bytes.")

    @staticmethod
    def _verify_int_alignment(hub_address, length, alignment):
        if alignment == 'length':
            if hub_address % length != 0:
                raise ValueError("The hub address is not aligned to the integer length (alignment='length' selected).")
            return
        if alignment == 'byte':
            return
        if alignment == 'word':
            if hub_address % 2 != 0:
                raise ValueError("The hub address is not word-aligned (alignment='word' selected).")
            return
        if alignment == 'long':
            if hub_address % 4 != 0:
                raise ValueError("The hub address is not long-aligned (alignment='long' selected).")
            return
        raise ValueError("Valid alignment options are 'length', 'byte', 'word', and 'long'.")


    # Token Methods

    def get_token(self, *, byteorder='little', signed=False):
        token_bytes = self.get_token_bytes()
        return int.from_bytes(token_bytes, byteorder, signed=signed)

    def set_token(self, token, *, byteorder='little', signed=False):
        if token < 0 and not signed:
            raise ValueError("Please use the 'signed=True' argument for negative numbers.") 
        token_bytes = token.to_bytes(4, byteorder, signed=signed)
        prev_token_bytes = self.set_token_bytes(token_bytes)
        return int.from_bytes(prev_token_bytes, byteorder, signed=signed)

    def get_token_bytes(self):
        transaction = self._send_command(6)
        return PeekPoke._parse_token_command(transaction)

    def set_token_bytes(self, token, *, use_padding=True):
        if len(token) < 4:
            if use_padding:
                new_token = bytearray(4)
                new_token[0:len(token)] = token[0:]
                token = new_token
            else:
                raise ValueError("The token must be exactly four bytes if padding is not used.")
        if len(token) > 4:
            raise ValueError("Too many bytes provided -- the token is a four-byte value.")
        transaction = self._send_command(7, token)
        return PeekPoke._parse_token_command(transaction)


    # Baudrate Methods

    @property
    def baudrate(self):
        return self._host.serial_port.get_baudrate(self._address)

    @baudrate.setter
    def baudrate(self, baudrate):
        self._host.serial_port.set_baudrate(self._address, baudrate)

    def switch_baudrate(self, baudrate, *, clkfreq=None, use_hub_clkfreq=False):
        """Sets both the local and remote baudrates."""
        if clkfreq is None:
            if use_hub_clkfreq:
                clkfreq = int.from_bytes(self._read_hub(0, 4), 'little')
            else:
                curr_baudrate = self.baudrate
                curr_timings = self._get_serial_timings()
                clkfreq = ( (curr_timings.bit_period_0 + curr_timings.bit_period_1) * curr_baudrate) / 2
        timings = SerialTimings()
        two_bit_period = int((2 * clkfreq) / baudrate)
        if two_bit_period < 52:
            raise ValueError("A baudrate of " + str(baudrate) + " bps is too fast given a clkfreq of " + str(clkfreq) + " MHz.")
        timings.bit_period_0 = two_bit_period >> 1
        timings.bit_period_1 = timings.bit_period_0 + (two_bit_period & 1)
        timings.start_bit_wait = max((timings.bit_period_0 >> 1) - 10, 5)
        timings.stop_bit_duration = int((10*clkfreq) / baudrate) - 5*timings.bit_period_0 - 4*timings.bit_period_1 + 1
        timings.interbyte_timeout = max(int(clkfreq/1000), 2*two_bit_period)  # max of 1ms or 4 bit periods
        timings.recovery_time = two_bit_period << 3
        # For the break multiple, use 1/2 of self._break_duration for dependable detection.
        timings.break_multiple = int((self._break_duration * clkfreq/2000) / timings.recovery_time)
        self._set_serial_timings(timings)
        self.baudrate = baudrate

    def revert_baudrate(self):
        """Changes the local baudrate back to the last known good value, and sends a break condition to the Propeller to instruct it to do the same."""
        if self._last_good_baudrate is None:
            raise RuntimeError("Cannot revert the baudrate before there has been a successful PeekPoke transaction using the current serial port and address.")
        self.baudrate = self._last_good_baudrate
        self._host.serial_port.serial.send_break(self._break_duration)


    # Internal Command Methods

    def _get_info(self):
        transaction = self._send_command(0)
        return PeekPoke._parse_get_info(transaction)

    def _read_hub(self, hub_address, count):
        # It is assumed that hub_address is in [0, 65535] and count is in [0, MAX_ATOMIC_READ].
        cmd_data = hub_address.to_bytes(2, 'little') + count.to_bytes(2, 'little')
        transaction = self._send_command(1, cmd_data)
        transaction.count = count
        return PeekPoke._parse_read_hub(transaction)

    def _write_hub(self, hub_address, data):
        # It is assumed that hub_address is in [0, 65535] and len(data) is in [0, MAX_ATOMIC_WRITE].
        cmd_data = hub_address.to_bytes(2, 'little') + len(data).to_bytes(2, 'little') + data
        transaction = self._send_command(2, cmd_data)
        PeekPoke._verify_essentials(transaction, 4)

    def _read_hub_str(self, hub_address, max_bytes):
        # It is assumed that hub_address is in [0, 65535] and count is in [0, MAX_ATOMIC_READ].
        cmd_data = hub_address.to_bytes(2, 'little') + max_bytes.to_bytes(2, 'little')
        transaction = self._send_command(3, cmd_data)
        transaction.max_bytes = max_bytes
        return PeekPoke._parse_read_hub_str(transaction)

    def _get_serial_timings(self):
        transaction = self._send_command(4)
        return PeekPoke._parse_get_serial_timings(transaction)

    def _set_serial_timings(self, timings):
        transaction = self._send_command(5, timings.get_as_binary())
        PeekPoke._verify_essentials(transaction, 4)

    def _payload_exec(self, block, response_expected=True):
        if len(block) < 8:
            raise ValueError("The block argument to payload_exec must have at least 8 bytes.")
        return self._send_command(8, block, response_expected)
        
    def _send_command(self, code, data=None, response_expected=True):
        command = bytearray(b'\x70\x70\x00') + code.to_bytes(1, 'little')
        if data is not None:
            command += data
        transaction = self._host.send_command(address=self._address, port=self._port, payload=command, response_expected=response_expected)
        transaction.command_code = code
        self._last_good_baudrate = self.baudrate
        return transaction


    # Internal Static Helper Methods

    @staticmethod
    def _verify_hub_args(hub_address, count, is_read, atomic):
        if hub_address < 0 or hub_address > 65535:
            raise ValueError("The hub address must be 0 to 65535.")
        if atomic:
            if is_read and count > PeekPoke.MAX_ATOMIC_READ:
                raise ValueError("An atomic hub read may not request more than " + str(PeekPoke.MAX_ATOMIC_READ) + " bytes.")
            if not is_read and count > PeekPoke.MAX_ATOMIC_WRITE:
                raise ValueError("An atomic hub write may not exceed " + str(PeekPoke.MAX_ATOMIC_WRITE) + " bytes.")
        if count < 0 or count > 65536:
            if is_read:
                raise ValueError("The hub read operation may request 0 to 65536 bytes.")
            else:
                raise ValueError("Hub writes may not exceed 65536 bytes.")

    @staticmethod
    def _verify_essentials(transaction, expected_size):
        # Verifies that the response has a valid initial header, and that it
        #  has the expected size (if specified).
        rsp = transaction.response
        if len(rsp) == 0:
            raise PeekPokeError(transaction, "The response is empty.")
        if len(rsp) < 4:
            raise PeekPokeError(transaction, "The response has less than four bytes.")
        if rsp[0] != 0x70 or rsp[1] != 0x70 or rsp[2] != 0x00:
            raise PeekPokeError(transaction, "The response identifier is incorrect.")
        if rsp[3] != transaction.command_code:
            raise PeekPokeError(transaction, "The response code is incorrect.")
        if expected_size is not None:
            if len(rsp) < expected_size:
                raise PeekPokeError(transaction, "The response has less than " + str(expected_size) + " bytes.")
            elif len(rsp) > expected_size:
                raise PeekPokeError(transaction, "The response has more than " + str(expected_size) + " bytes.")

    @staticmethod
    def _parse_get_info(transaction):
        PeekPoke._verify_essentials(transaction, 10)
        rsp = transaction.response
        info = PeekPokeInfo()
        info.layoutID = int.from_bytes(rsp[4:8], 'little')
        info.par = int.from_bytes(rsp[8:10], 'little')
        return info

    @staticmethod
    def _parse_read_hub(transaction):
        PeekPoke._verify_essentials(transaction, transaction.count + 4)
        return transaction.response[4:]

    @staticmethod
    def _parse_read_hub_str(transaction):
        PeekPoke._verify_essentials(transaction, None)
        rsp = transaction.response
        expected_max_size = transaction.max_bytes + 4
        if len(rsp) > expected_max_size:
            raise PeekPokeError(transaction, "The response has more data than requested.")
        elif transaction.max_bytes != 0 and len(rsp) == 4:
            raise PeekPokeError(transaction, "The response unexpectedly did not return any data.")
        return rsp[4:]

    @staticmethod
    def _parse_get_serial_timings(transaction):
        PeekPoke._verify_essentials(transaction, 32)
        return SerialTimings(binary=transaction.response[4:32])

    @staticmethod
    def _parse_token_command(transaction):
        # getToken and setToken both return an 8 byte response where the
        #  last four bytes are a token (either current or previous value).
        PeekPoke._verify_essentials(transaction, 8)
        return transaction.response[4:8]


class PeekPokeError(ClientError):
    def __init__(self, transaction, message):
        super().__init__(transaction.address, transaction.port, message)
        self.command_code = transaction.command_code
    def __str__(self):
        return super().extra_str() + " Command code: " + str(self.command_code) + "."


class PeekPokeInfo():
    def __init__(self):
        self.layoutID = None
        self.par = None


class SerialTimings():

    def __init__(self, binary=None):
        self.bit_period_0 = 0
        self.bit_period_1 = 0  
        self.start_bit_wait = 0  
        self.stop_bit_duration = 0
        self.interbyte_timeout = 0
        self.recovery_time = 0
        self.break_multiple = 0 
        if binary is not None:
            self.set_from_binary(binary)

    def __str__(self):
        return "PropCR serial timings; bit_period_0: " + str(self.bit_period_0) + ", bit_period_1: " + str(self.bit_period_1) + ", start_bit_wait: " + str(self.start_bit_wait) + ", stop_bit_duration: " + str(self.stop_bit_duration) + ", interbyte_timeout: " + str(self.interbyte_timeout) + ", recovery_time: " + str(self.recovery_time) + ", break_multiple: " + str(self.break_multiple) + "."

    def get_as_binary(self):
        binary = bytearray()
        binary += self.bit_period_0.to_bytes(4, 'little')
        binary += self.bit_period_1.to_bytes(4, 'little')
        binary += self.start_bit_wait.to_bytes(4, 'little')
        binary += self.stop_bit_duration.to_bytes(4, 'little')
        binary += self.interbyte_timeout.to_bytes(4, 'little')
        binary += self.recovery_time.to_bytes(4, 'little')
        binary += self.break_multiple.to_bytes(4, 'little')
        return binary

    def set_from_binary(self, binary):
        # Assumes binary is bytes-like and first 32 bytes are in expected format.
        self.bit_period_0       = int.from_bytes(binary[0:4], 'little')
        self.bit_period_1       = int.from_bytes(binary[4:8], 'little')
        self.start_bit_wait     = int.from_bytes(binary[8:12], 'little')
        self.stop_bit_duration  = int.from_bytes(binary[12:16], 'little')
        self.interbyte_timeout  = int.from_bytes(binary[16:20], 'little')
        self.recovery_time      = int.from_bytes(binary[20:24], 'little')
        self.break_multiple     = int.from_bytes(binary[24:28], 'little')

