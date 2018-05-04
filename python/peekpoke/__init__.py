# PeekPoke
# 4 May 2018
# Chris Siedell
# source: https://github.com/chris-siedell/PeekPoke
# python: https://pypi.org/project/peekpoke/
# homepage: http://siedell.com/projects/PeekPoke/


# todo: enforce more local checks and make baudrate behavior 
#       smarter by using cached device info 
# todo: revise if break callbacks added to Crow host


from crow.host import Host
from crow.host_serial import HostSerialSettings
from crow.errors import ClientError
from crow.errors import InvalidCommandError
from crow.errors import ServiceError


__version__ = '0.6.3'
VERSION = __version__


class PeekPoke():

    def __init__(self, serial_port_name, address=1, port=112):
        if address < 1 or address > 31:
            raise ValueError("The address must be 1 to 31.")
        if port < 0 or port > 255:
            raise ValueError("The port must be 0 to 255.")
        self._address = address
        self._port = port
        self._host = Host(serial_port_name)
        self._host.custom_service_error_callback = self._custom_error_callback
        self._select_propcr_order()
        self._last_good_baudrate = None
        self._info = None
        self._break_duration = 400

    @property
    def serial_port_name(self):
        return self._host.serial_port.name

    @serial_port_name.setter
    def serial_port_name(self, serial_port_name):
        self._revert_propcr_order()
        try:
            self._host = Host(serial_port_name)
            # Reset the following only on success.
            self._last_good_baudrate = None
            self._info = None
        finally:
            self._select_propcr_order()

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
        self._info = None

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, port):
        if port < 0 or port > 255:
            raise ValueError("The port must be 0 to 255.")
        self._port = port
        self._info = None

    @property
    def baudrate(self):
        return self._host.serial_port.get_baudrate(self._address)

    @baudrate.setter
    def baudrate(self, baudrate):
        self._host.serial_port.set_baudrate(self._address, baudrate)


    # Hub Memory: Binary Data Methods

    def get_bytes(self, hub_address, count, *, atomic=False):
        self._verify_hub_args(hub_address, count, True, atomic)
        info = self.get_info()
        result = bytearray()
        while count > 0:
            atomic_count = min(count, info.max_atomic_read)
            count -= atomic_count
            result += self._read_hub(hub_address, atomic_count)
            hub_address = (hub_address + atomic_count)%65536
        return result

    def set_bytes(self, hub_address, data, *, atomic=False):
        count = len(data)
        self._verify_hub_args(hub_address, count, False, atomic)
        info = self.get_info()
        index = 0
        while count > 0:
            atomic_count = min(count, info.max_atomic_write)
            count -= atomic_count
            self._write_hub(hub_address, data[index:index+atomic_count])
            hub_address = (hub_address + atomic_count)%65536
            index += atomic_count

    def fill_bytes(self, hub_address, num_bytes, pattern, *, atomic=False):
        data = bytearray(num_bytes)
        if pattern != b'\x00':
            pattern_len = len(pattern)
            if pattern_len == 0:
                raise ValueError("The pattern must not be empty.")
            index = 0
            while index < num_bytes:
                n = min(pattern_len, num_bytes-index)
                data[index:index+n] = pattern[0:n]
                index += n
        # set_bytes will verify hub args.
        self.set_bytes(hub_address, data, atomic=atomic)


    # Hub Memory: String Methods

    def get_str(self, hub_address, max_bytes, *, encoding='latin_1', errors='replace', nul_terminated=True, atomic=False):
        self._verify_hub_args(hub_address, max_bytes, True, atomic)
        info = self.get_info()
        result = bytearray()
        if nul_terminated:
            while max_bytes > 0:
                atomic_max_bytes = min(max_bytes, info.max_atomic_read)
                max_bytes -= atomic_max_bytes
                result += self._read_hub_str(hub_address, atomic_max_bytes)
                hub_address = (hub_address + atomic_max_bytes)%65536
                if result[-1] == 0:
                    break
        else:
            while max_bytes > 0:
                atomic_count = min(max_bytes, info.max_atomic_read)
                max_bytes -= atomic_count
                result += self._read_hub(hub_address, atomic_count)
                hub_address = (hub_address + atomic_count)%65536
        if len(result) == 0:
            return ''
        if nul_terminated and result[-1] == 0:
            return result[:-1].decode(encoding=encoding, errors=errors)
        else:
            return result.decode(encoding=encoding, errors=errors)

    def set_str(self, hub_address, max_bytes, string, *, encoding='latin_1', errors='replace', nul_terminated=True, truncate=False, atomic=False):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero.")
        data = string.encode(encoding=encoding, errors=errors)
        if nul_terminated:
            if len(data) >= max_bytes:
                if truncate:
                    data = bytearray(data[0:max_bytes-1]) + b'\x00'
                else:
                    raise ValueError("The encoded string size (" + str(len(data)) + ") plus the terminating NUL exceeds the max_bytes limit (" + str(max_bytes) + ").")
            else:
                data = bytearray(data) + b'\x00'
        else:
            if len(data) > max_bytes:
                if truncate:
                    data = data[0:max_bytes]
                else:
                    raise ValueError("The encoded string size (" + str(len(data)) + ") exceeds the max_bytes limit (" + str(max_bytes) + ").")
        # set_bytes will verify hub args.
        self.set_bytes(hub_address, data, atomic=atomic)


    # Hub Memory: Integer Methods

    def get_int(self, hub_address, length, *, alignment='length', byteorder='little', signed=False):
        PeekPoke._verify_int_length(length)
        self._verify_hub_args(hub_address, length, True, True)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        data = self._read_hub(hub_address, length)
        return int.from_bytes(data, byteorder, signed=signed)

    def set_int(self, hub_address, length, integer, *, alignment='length', byteorder='little', signed=False):
        PeekPoke._verify_int_length(length)
        self._verify_hub_args(hub_address, length, False, True)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        data = integer.to_bytes(length, byteorder, signed=signed)
        self._write_hub(hub_address, data)

    def get_ints(self, hub_address, length, count, *, alignment='length', byteorder='little', signed=False, atomic=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        # get_bytes will verify hub args.
        num_bytes = count*length
        data = self.get_bytes(hub_address, num_bytes, atomic=atomic)
        integers = []
        index = 0
        for _i in range(0, count):
            integers.append(int.from_bytes(data[index:index+length], byteorder, signed=signed))
            index += length
        return integers

    def set_ints(self, hub_address, length, integers, *, alignment='length', byteorder='little', signed=False, atomic=False):
        PeekPoke._verify_int_length(length)
        PeekPoke._verify_int_alignment(hub_address, length, alignment)
        # set_bytes will verify hub args.
        data = bytearray()
        for i in integers:
            data += i.to_bytes(length, byteorder, signed=signed)
        self.set_bytes(hub_address, data, atomic=atomic)


    # Baudrate Methods

    def switch_baudrate(self, baudrate, *, clkfreq=None, use_hub_clkfreq=False):
        """Sets both the local and remote baudrates."""
        if clkfreq is None:
            if use_hub_clkfreq:
                clkfreq = int.from_bytes(self._read_hub(0, 4), 'little')
            else:
                clkfreq = self.estimate_clkfreq()
        two_bit_period = int((2 * clkfreq) / baudrate)
        if two_bit_period < 52:
            raise ValueError("A baudrate of " + str(baudrate) + " bps is too fast given a clkfreq of " + str(clkfreq) + " MHz.")
        timings = SerialTimings()
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


    # Token Methods

    def get_token(self, *, byteorder='little', signed=False):
        token_bytes = self.get_token_bytes()
        return int.from_bytes(token_bytes, byteorder, signed=signed)

    def set_token(self, token, *, byteorder='little', signed=False):
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
        elif len(token) > 4:
            raise ValueError("Too many bytes provided -- the token is a four-byte value.")
        transaction = self._send_command(7, token)
        return PeekPoke._parse_token_command(transaction)


    # Miscellaneous Methods

    def get_par(self, *, use_cached=True):
        info = self.get_info(use_cached=use_cached)
        return info.par

    def get_identifier(self, *, use_cached=True):
        info = self.get_info(use_cached=use_cached)
        return info.identifier

    def get_info(self, *, use_cached=True):
        if not use_cached or self._info is None:
            self._info = self._get_info()
        return self._info

    def estimate_clkfreq(self):
        timings = self._get_serial_timings()
        return ( (timings.bit_period_0 + timings.bit_period_1) * self.baudrate) / 2.0


    # Internal Command Methods

    def _get_info(self):
        transaction = self._send_command(0)
        return PeekPoke._parse_get_info(transaction)

    def _read_hub(self, hub_address, count):
        # It is assumed that hub_address is in [0, 65535] and count is in [0, max_atomic_read],
        #  and there is no wrap around.
        cmd_data = hub_address.to_bytes(2, 'little') + count.to_bytes(2, 'little')
        transaction = self._send_command(1, cmd_data)
        transaction.count = count
        return PeekPoke._parse_read_hub(transaction)

    def _write_hub(self, hub_address, data):
        # It is assumed that hub_address is in [0, 65535] and len(data) is in [0, max_atomic_write],
        #  and there is no wrap around.
        cmd_data = hub_address.to_bytes(2, 'little') + len(data).to_bytes(2, 'little') + data
        transaction = self._send_command(2, cmd_data)
        PeekPoke._verify_essentials(transaction, 4, 4)

    def _read_hub_str(self, hub_address, max_bytes):
        # It is assumed that hub_address is in [0, 65535] and count is in [0, max_atomic_read],
        #  and there is no wrap around.
        cmd_data = hub_address.to_bytes(2, 'little') + max_bytes.to_bytes(2, 'little')
        transaction = self._send_command(3, cmd_data)
        transaction.max_bytes = max_bytes
        return PeekPoke._parse_read_hub_str(transaction)

    def _get_serial_timings(self):
        transaction = self._send_command(4)
        return PeekPoke._parse_get_serial_timings(transaction)

    def _set_serial_timings(self, timings):
        transaction = self._send_command(5, timings.as_bytes())
        PeekPoke._verify_essentials(transaction, 4, 4)

    def _payload_exec(self, block, response_expected=True):
        if len(block) < 8:
            raise ValueError("The block argument to payload_exec must have at least eight bytes.")
        return self._send_command(8, block, response_expected)
        
    def _send_command(self, command_code, data=None, response_expected=True):
        command = bytearray(b'\x70\x70\x00') + command_code.to_bytes(1, 'little')
        if data is not None:
            command += data
        transaction = self._host.send_command(address=self._address, port=self._port, payload=command, response_expected=response_expected, context=command)
        transaction.command_code = command_code
        self._last_good_baudrate = self.baudrate
        return transaction

    def _custom_error_callback(self, address, port, number, details, context):
        # This method is called if the host receives an error response with
        #  numbers 128 to 255. The host will raise a generic ServiceError if
        #  this method returns.
        # The only expected custom error number is 128.
        if number == 128:
            # context is just the command payload, from which we can extract
            #  details to add to the dictionary.
            if len(context) < 8:
                raise ClientError(address, port, "Error number 128 (AccessError) returned from device, but the initiating command payload had less than eight bytes.")
            details['command_code'] = context[3]
            details['hub_address'] = int.from_bytes(context[4:6], 'little')
            details['count'] = int.from_bytes(context[6:8], 'little')
            # Add string version of command.
            if context[3] == 1:
                details['command'] = "read_hub"
            elif context[3] == 2:
                details['command'] = "write_hub"
            elif context[3] == 3:
                details['command'] = "read_hub_str"
            # Add allowed ranges, if cached.
            if self._info is not None:
                if context[3] == 1 or context[3] == 3:
                    details['min_read_address'] = self._info.min_read_address
                    details['max_read_address'] = self._info.max_read_address
                elif context[3] == 2:
                    details['min_write_address'] = self._info.min_write_address
                    details['max_write_address'] = self._info.max_write_address
            raise AccessError(self._address, self._port, number, details)


    # Internal Helper Methods

    def _verify_hub_args(self, hub_address, count, is_read, atomic):
        # Used by hub memory methods to verify arguments.
        if hub_address < 0 or hub_address > 65535:
            raise ValueError("The hub address must be 0 to 65535.")
        if atomic:
            info = self.get_info()
            if is_read and count > info.max_atomic_read:
                raise ValueError("An atomic hub read may not request more than " + str(info.max_atomic_read) + " bytes.")
            if not is_read and count > info.max_atomic_write:
                raise ValueError("An atomic hub write may not exceed " + str(info.max_atomic_write) + " bytes.")
        if count < 0 or count > 65536:
            if is_read:
                raise ValueError("The hub read operation may request 0 to 65536 bytes.")
            else:
                raise ValueError("Hub writes may not exceed 65536 bytes.")
        if hub_address + count > 65536:
            raise ValueError("Hub memory operations may not wrap around the end of the hub address space.")

    # The save and revert technique being used here can 'fix' the default propcr order.
    #  The underlying settings object for the address will initially have propcr_order=None,
    #  meaning that the default for the serial port should be used. If it was None when select
    #  was called, then when revert is called it will be set to whatever the default was when
    #  select was previously called.
    # I don't think this will be a problem in practice.

    def _revert_propcr_order(self):
        # Call before the host or address will change.
        # Reversion occurs only if there has not been a successful communication
        #  with the host and address.
        if self._last_good_baudrate is None:
            self._host.serial_port.set_propcr_order(self._address, self._prev_propcr_order)

    def _select_propcr_order(self):
        # Call after the host or address has changed.
        self._prev_propcr_order = self._host.serial_port.get_propcr_order(self._address)
        self._host.serial_port.set_propcr_order(self._address, True)


    # Static Internal Helper Methods

    @staticmethod
    def _verify_int_length(length):
        if length != 1 and length != 2 and length != 4 and length != 8:
            raise ValueError("Valid integer lengths are 1, 2, 4, and 8 bytes.")

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

    @staticmethod
    def _verify_essentials(transaction, min_size, max_size):
        # Verifies that the response has a valid initial header, and that its
        #  size is in the expected range (which may be open ended at both limits).
        rsp = transaction.response
        if len(rsp) == 0:
            raise PeekPokeError(transaction, "The response is empty.")
        if len(rsp) < 4:
            raise PeekPokeError(transaction, "The response has less than four bytes.")
        if rsp[0] != 0x70 or rsp[1] != 0x70 or rsp[2] != 0x00:
            raise PeekPokeError(transaction, "The response identifier is incorrect.")
        if rsp[3] != transaction.command_code:
            raise PeekPokeError(transaction, "The response code is incorrect.")
        if min_size is not None and len(rsp) < min_size:
            raise PeekPokeError(transaction, "The response has less than " + str(min_size) + " bytes.")
        if max_size is not None and len(rsp) > max_size:
            raise PeekPokeError(transaction, "The response has more than " + str(max_size) + " bytes.")

    @staticmethod
    def _parse_get_info(transaction):
        PeekPoke._verify_essentials(transaction, 30, None)
        return PeekPokeInfo(transaction.response)

    @staticmethod
    def _parse_read_hub(transaction):
        expected_size = transaction.count + 4
        PeekPoke._verify_essentials(transaction, expected_size, expected_size)
        return transaction.response[4:]

    @staticmethod
    def _parse_read_hub_str(transaction):
        PeekPoke._verify_essentials(transaction, None, transaction.max_bytes + 4)
        rsp = transaction.response
        if transaction.max_bytes != 0 and len(rsp) == 4:
            raise PeekPokeError(transaction, "The read_hub_str response unexpectedly did not return any data.")
        return rsp[4:]

    @staticmethod
    def _parse_get_serial_timings(transaction):
        PeekPoke._verify_essentials(transaction, 5, None)
        try:
            return SerialTimings(data=transaction.response[4:])
        except ValueError as e:
            raise PeekPokeError(transaction, str(e))

    @staticmethod
    def _parse_token_command(transaction):
        # getToken and setToken both return an 8 byte response where the
        #  last four bytes are a token (either current or previous value).
        PeekPoke._verify_essentials(transaction, 8, 8)
        return transaction.response[4:8]


class AccessError(InvalidCommandError):
    def __init__(self, address, port, number, details):
        super().__init__(address, port, number, details)
    def __str__(self):
        return "The requested hub memory operation is outside the allowed range. " + super().extra_str()


class PeekPokeError(ClientError):
    def __init__(self, transaction, message):
        super().__init__(transaction.address, transaction.port, message)
        self.command_code = transaction.command_code
    def __str__(self):
        return super().extra_str() + " Command code: " + str(self.command_code) + "."


class PeekPokeInfo():

    def __init__(self, response=None):
        if response is not None:
            self.set_from_response(response)

    def set_from_response(self, response):
        self.max_atomic_read = int.from_bytes(response[4:6], 'little')
        self.max_atomic_write = int.from_bytes(response[6:8], 'little')
        self.min_read_address = int.from_bytes(response[8:10], 'little')
        self.max_read_address = int.from_bytes(response[10:12], 'little')
        self.min_write_address = int.from_bytes(response[12:14], 'little')
        self.max_write_address = int.from_bytes(response[14:16], 'little')
        self.layout_id = response[16:20]
        self.identifier = int.from_bytes(response[20:24], 'little')
        self.par = int.from_bytes(response[24:26], 'little')
        self.available_commands_bitmask = int.from_bytes(response[26:28], 'little')
        self.serial_timings_format = response[28]
        self.peekpoke_version = response[29]

    def __str__(self):
        return "PeekPoke instance info, max_atomic_read: " + str(self.max_atomic_read) + ", max_atomic_write: " + str(self.max_atomic_write) + ", min_read_address: " + str(self.min_read_address) + ", max_read_address: " + str(self.max_read_address) + ", min_write_address: " + str(self.min_write_address) + ", max_write_address: " +str(self.max_write_address) + ", layout_id: [" + self.layout_id.hex() + "], identifier: " + str(self.identifier) + ", par: " + str(self.par) + ", available_commands_bitmask: {:#4x}".format(self.available_commands_bitmask) + ", serial_timings_format: " + str(self.serial_timings_format) + ", peekpoke_version: " + str(self.peekpoke_version) + "."


class SerialTimings():

    def __init__(self, *, data=None):
        self.bit_period_0 = 0
        self.bit_period_1 = 0  
        self.start_bit_wait = 0  
        self.stop_bit_duration = 0
        self.interbyte_timeout = 0
        self.recovery_time = 0
        self.break_multiple = 0 
        if data is not None:
            self.set_from_bytes(data)

    @property
    def format(self):
        return 0

    def __str__(self):
        return "Serial timings, format: 0, bit_period_0: " + str(self.bit_period_0) + ", bit_period_1: " + str(self.bit_period_1) + ", start_bit_wait: " + str(self.start_bit_wait) + ", stop_bit_duration: " + str(self.stop_bit_duration) + ", interbyte_timeout: " + str(self.interbyte_timeout) + ", recovery_time: " + str(self.recovery_time) + ", break_multiple: " + str(self.break_multiple) + "."

    def as_bytes(self):
        # The first byte is format (0), the next three are padding.
        data = bytearray(4)           
        data += self.bit_period_0.to_bytes(4, 'little')
        data += self.bit_period_1.to_bytes(4, 'little')
        data += self.start_bit_wait.to_bytes(4, 'little')
        data += self.stop_bit_duration.to_bytes(4, 'little')
        data += self.interbyte_timeout.to_bytes(4, 'little')
        data += self.recovery_time.to_bytes(4, 'little')
        data += self.break_multiple.to_bytes(4, 'little')
        return data

    def set_from_bytes(self, data):
        # The following byte positions differ from the specification since
        #  the initial header is not included.
        if len(data) == 0:
            raise ValueError("The serial timings data must not be empty.")
        if data[0] != 0:
            raise ValueError("The serial timings format (" + str(data[0]) + ") is not supported.")
        if len(data) != 32:
            raise ValueError("The serial timings data has the wrong size (expected 32 bytes, got " + str(len(data)) + ").")
        self.bit_period_0       = int.from_bytes(data[4:8], 'little')
        self.bit_period_1       = int.from_bytes(data[8:12], 'little')
        self.start_bit_wait     = int.from_bytes(data[12:16], 'little')
        self.stop_bit_duration  = int.from_bytes(data[16:20], 'little')
        self.interbyte_timeout  = int.from_bytes(data[20:24], 'little')
        self.recovery_time      = int.from_bytes(data[24:28], 'little')
        self.break_multiple     = int.from_bytes(data[28:32], 'little')

