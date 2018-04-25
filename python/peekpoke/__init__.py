# PeekPoke
# 25 April 2018
# Chris Siedell
# source: https://github.com/chris-siedell/PeekPoke
# python: https://pypi.org/project/peekpoke/
# homepage: http://siedell.com/projects/PeekPoke/


from crow.host import Host
from crow.host_serial import HostSerialSettings
from crow.errors import ClientError


__version__ = '0.4.0'
VERSION = __version


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

    def get_par(self):
        transaction = self._send_command(0)
        return PeekPoke.parse_get_par(transaction)

    def _check_hub_address(self, hub_address):
        if hub_address < 0 or hub_address > 65535:
            raise ValueError("hub_address must be 0 to 65535.")

    def read_hub(self, hub_address, count):
        self._check_hub_address(hub_address)
        if count < 0 or count > 65536:
            raise ValueError("count must be 0 to 65536.")
        result = bytearray()
        while count > 0:
            atomic_count = min(count, PeekPoke.MAX_ATOMIC_READ)
            count -= atomic_count
            result += self.atomic_read_hub(hub_address, atomic_count)
            hub_address = (hub_address + atomic_count)%65536
        return result

    def atomic_read_hub(self, hub_address, count):
        self._check_hub_address(hub_address)
        if count < 0 or count > PeekPoke.MAX_ATOMIC_READ:
            raise ValueError("Atomic hub reads may not exceed " + str(PeekPoke.MAX_ATOMIC_READ) + " bytes.")
        data = hub_address.to_bytes(2, 'little') + count.to_bytes(2, 'little')
        transaction = self._send_command(1, data)
        transaction.count = count
        return PeekPoke.parse_read_hub(transaction)

    def write_hub(self, hub_address, data):
        self._check_hub_address(hub_address)
        count = len(data)
        if count > 65536:
            raise ValueError("Hub writes can not exceed 65536 bytes.")
        index = 0
        while count > 0:
            atomic_count = min(count, PeekPoke.MAX_ATOMIC_WRITE)
            count -= atomic_count
            self.atomic_write_hub(hub_address, data[index:index+atomic_count])
            hub_address = (hub_address + atomic_count)%65536
            index += atomic_count

    def atomic_write_hub(self, hub_address, data):
        self._check_hub_address(hub_address)
        count = len(data)
        if count > PeekPoke.MAX_ATOMIC_WRITE:
            raise ValueError("Atomic hub writes may not exceed " + str(PeekPoke.MAX_ATOMIC_WRITE) + " bytes.")
        cmd_data = hub_address.to_bytes(2, 'little') + count.to_bytes(2, 'little') + data
        transaction = self._send_command(2, cmd_data)
        PeekPoke.validate_header(transaction)

    @property
    def baudrate(self):
        return self._host.serial_port.get_baudrate(self._address)

    @baudrate.setter
    def baudrate(self, baudrate):
        self._host.serial_port.set_baudrate(self._address, baudrate)

    def switch_baudrate(self, baudrate, *, clkfreq=None, use_hub_clkfreq=False):
        """Sets both the local and remote baudrates."""
        # In order to set the serial timings the Propeller's system clock frequency (clkfreq)
        #  must be known or estimated. Here are the three ways this can be done, listed in the
        #  order of priority:
        #   - use a value provided with the call to this method (clkfreq argument is not None),
        #   - use the first long of hub ram (use_hub_clkfreq argument is True),
        #   - estimate the clock frequency given the current baudrate (default).
        # Estimating the clock frequency may introduce errors that grow after multiple switches.
        if clkfreq is None:
            if use_hub_clkfreq:
                clkfreq = int.from_bytes(self.atomic_read_hub(0, 4), 'little')
            else:
                curr_baudrate = self.baudrate
                curr_timings = self._get_serial_timings()
                clkfreq = ( (curr_timings.bit_period_0 + curr_timings.bit_period_1) * curr_baudrate) / 2
        timings = SerialTimings()
        two_bit_period = int((2 * clkfreq) / baudrate)
        if two_bit_period < 52:
            raise ValueError("The baudrate " + str(baudrate) + " bps is too fast given a clkfreq of " + str(clkfreq) + " MHz.")
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

    def _get_serial_timings(self):
        transaction = self._send_command(3)
        return PeekPoke.parse_get_serial_timings(transaction)

    def _set_serial_timings(self, timings):
        transaction = self._send_command(4, timings.get_as_binary())
        PeekPoke.validate_header(transaction)

    def _payload_exec(self, code, response_expected=True):
        if len(code) < 4:
            raise ValueError("There must be at least 4 bytes of code for payload_exec.")
        return self._send_command(5, code, response_expected)
        
    def _send_command(self, code, data=None, response_expected=True):
        command = bytearray(b'\x70\x70\x00') + code.to_bytes(1, 'little')
        if data is not None:
            command += data
        transaction = self._host.send_command(address=self._address, port=self._port, payload=command, response_expected=response_expected)
        transaction.command_code = code
        self._last_good_baudrate = self.baudrate
        return transaction

    @staticmethod
    def validate_header(transaction):
        rsp = transaction.response
        if len(rsp) == 0:
            raise PeekPokeError(transaction, "The response is empty.")
        if len(rsp) < 4:
            raise PeekPokeError(transaction, "The response has fewer than four bytes.")
        if rsp[0] != 0x70 or rsp[1] != 0x70 or rsp[2] != 0x00:
            raise PeekPokeError(transaction, "The response identifier is incorrect.")
        if rsp[3] != transaction.command_code:
            raise PeekPokeError(transaction, "The response code is incorrect.")

    @staticmethod
    def parse_get_par(transaction):
        PeekPoke.validate_header(transaction)
        rsp = transaction.response
        if len(rsp) < 6:
            raise PeekPokeError(transaction, "The response is less than six bytes.")
        return int.from_bytes(rsp[4:6], 'little')

    @staticmethod
    def parse_read_hub(transaction):
        PeekPoke.validate_header(transaction)
        rsp = transaction.response
        expected_size = transaction.count + 4
        if len(rsp) < expected_size:
            raise PeekPokeError(transaction, "The response has less data than requested.")
        return rsp[4:expected_size]

    @staticmethod
    def parse_get_serial_timings(transaction):
        PeekPoke.validate_header(transaction)
        rsp = transaction.response
        if len(rsp) < 32:
            raise PeekPokeError(transaction, "The response has less than 32 bytes.")
        return SerialTimings(binary=rsp[4:32])


class PeekPokeError(ClientError):
    def __init__(self, transaction, message):
        super().__init__(transaction.address, transaction.port, message)
    def __str__(self):
        return super().extra_str()


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

