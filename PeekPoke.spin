{
==================================================
PeekPoke.spin
Version 0.6.1 (alpha/experimental)
1 May 2018
Chris Siedell
source: https://github.com/chris-siedell/PeekPoke
python: https://pypi.org/project/peekpoke/
homepage: http://siedell.com/projects/PeekPoke/
==================================================

  PeekPoke is a utility for reading and writing a Propeller's hub RAM from a PC. It
is entirely cog-contained after launch.

  PeekPoke allows the serial timings to be changed remotely (this feature can be
disabled). By default, if a break condition is detected the serial parameters will
be reset to their last known good values.

  If the payloadExec feature is enabled PeekPoke will allow the PC to execute
arbitrary code, effectively allowing any command that can be implemented in the
space available.

  By default, all features of PeekPoke except payloadExec are enabled. There are
Spin methods that can enable and disable some features.

  Each PeekPoke instance requires a unique address on the serial line (addresses
may be 1 to 31, 1 is the default). PeekPoke uses port 112 by default, but this
may be changed.

  The following methods are available to change the default settings before launch.
Some must be called in a particular sequence.

    setPins(rxPin, txPin)
    setBaudrate(baudrate)
    setInterbyteTimeoutInMS(milliseconds) - if called, MUST follow setBaudrate
    setInterbyteTimeoutInBitPeriods(count) - if called, MUST follow setBaudrate
    setRecoveryTimeInMS(milliseconds)
    setRecoveryTimeInBitPeriods(count) - if called, MUST follow setBaudrate
    setBreakThresholdInMS(milliseconds) - MUST be called if setRecoveryTime* is called
    setAddress(address)
    setPort(port)
    enableWriteHub
    disableWriteHub
    enableSetSerialTimings
    disableSetSerialTimings
    enablePayloadExec
    disablePayloadExec
    enableBreakDetection
    disableBreakDetection
    setReadRange(minAddr, maxAddr)
    setWriteRange(minAddr, maxAddr)
    setIdentifier(identifier)
  
  If the recovery time is set, then setBreakThresholdInMS must be called afterwards
in order to recalculate the break multiple, regardless if the threshold has changed.

  The addresses for the allowed read and write ranges must be in [0, 0xffff] and
minAddr must be less than maxAddr (no wrap around). Both endpoints are inclusive. The
range of a remote command must be entirely within the allowed range or it will not be
performed.

  The identifier is a four byte constant that may be used to identify the project.
The PC obtains its value using the getInfo command.

  Calling the above methods has no effect on already launched instances.

  Launching an instance is done with one of two methods:

    new(par) - returns cogID + 1 (will be 0 if no cog free)
    init(cogID, par)

  The par argument will be passed to the launched instance using the PAR register.
The PC can use the getInfo command to obtain its value. Keep in mind that PAR is a
two-byte value where the bottom two bits are always zero.

  The launching methods will not return until the new instance is completely loaded,
so calling code may immediately prepare to launch another instance.

  Since this implementation uses PropCR, make sure to use PropCR byte ordering when
sending a command.

  This version was originally built using PropCR-BD 0.3.2 (24 April 2018).
}


con

    { Compile-Time Constants }
    cNumPayloadRegisters        = 56                        'MUST be even
    cMaxPayloadSize             = 4*cNumPayloadRegisters
    
    { Default Settings
        These settings may be changed before cog launch -- see Spin methods.
    }
    cClkfreq                    = 80_000_000    'used just for calculating derived default settings
    cRxPin                      = 31            'must be 0-31
    cTxPin                      = 30            'must be 0-31
    cBaudrate                   = 115200        'the minimum supported bit period (clkfreq/baudrate) is 26 clocks
    cInterbyteTimeoutInMS       = 1
    cRecoveryTimeInBitPeriods   = 16            'recoveryTime should be greater than a byte period
    cBreakThresholdInMS         = 150
    cAddress                    = 1             'must be 1-31
    cUserPort                   = 112           'PeekPoke uses 112 by default
    
    { Derived Default Settings }
    cTwoBitPeriod = (2*cClkfreq) / cBaudrate
    cBitPeriod0 = cTwoBitPeriod >> 1
    cBitPeriod1 = cBitPeriod0 + (cTwoBitPeriod & 1) 
    cStartBitWait = (cBitPeriod0 >> 1) - 10 #> 5
    cStopBitDuration = ((10*cClkfreq) / cBaudrate) - 5*cBitPeriod0 - 4*cBitPeriod1 + 1
    cTimeout = (cClkfreq/1000) * cInterbyteTimeoutInMS
    cRecoveryTime = cBitPeriod0 * cRecoveryTimeInBitPeriods
    cBreakMultiple = ((cClkfreq/1000) * cBreakThresholdInMS) / cRecoveryTime #> 1
    
    { Flags and Masks for packetInfo (which is CH2). }
    cRspExpectedFlag        = $80
    cAddressMask            = %0001_1111
    
    { Crow Error Response Numbers
        Error numbers 0-63 should be used only by PropCR code (the device implementation). }
    cOversizedCommand           = 6
    cPortNotOpen                = 8

    {   The following error constants may be used by the service (i.e. the user code), but these
      are the only numbers in the range 64-127 that should be used -- the rest have been reserved
      for future assignement.
        The numbers 128-255 are available for custom assignment by the service code. }
    cServiceError               = 64
    cUnknownCommandFormat       = 65
    cRequestTooLarge            = 66
    cServiceLowResources        = 67
    cCommandNotAvailable        = 68
    cCommandNotImplemented      = 69
    cCommandNotAllowed          = 70
    cInvalidCommand             = 71
    cIncorrectCommandSize       = 72
    cMissingCommandData         = 73
    cTooMuchCommandData         = 74
    
    { Special Purpose Registers
        To save space, PropCR makes use of some special purpose registers. The following SPRs are used for
      variables and temporaries: sh-par, sh-cnt, sh-ina, sh-inb, outb, dirb, vcfg, and vscl.
        The "_SH" suffix is a reminder to always used the variable/temporary as a destination register.
        PropCR uses the counter B module in RecoveryMode (when waiting for rx line idle or detecting breaks).
        PropCR never uses the counter A module or its registers -- it leaves it free for custom use.
        PropCR does not use the actual PAR register (only the shadow register), so it is free for custom use.
    }
    _txWait_SH          = $1f0  'sh-par
    _rxPort_SH          = $1f0  'sh-par
    
    _txByteNum_SH       = $1f1  'sh-cnt
    _rxTmp_SH           = $1f1  'sh-cnt
    
    _txBitCountdown_SH  = $1f2  'sh-ina
    _rxCH0inc_SH        = $1f2  'sh-ina - CH0 (incomplete -- does not include bit 7) is saved in-loop for reserved bits testing
   
    _rxF16U_SH          = $1f3  'sh-inb
    
    token               = $1f5  'outb - token is assigned in the recieve loop; this register is also used for composing the response header (unsuitable as nop)
    packetInfo          = $1f7  'dirb -  packetInfo is CH2; potential nop; upper bytes always set to 0 (from _rxByte)
    sendBufferPointer   = $1fe  'vcfg - (video generator is off if bits 29-30 are zero); points to Payload (0) by default; should always be 9-bit value; potential nop
    
    'Important: the upper bytes of _rxByte (i.e. VSCL) must be zero before ReceiveCommand is executed.
    _txByte             = $1ff  'vscl - same as for _rxByte (upper bytes temporarily non-zero until masked, so not suitable for vcfg or ctrx, but ok to alias _rxByte)
    _rxByte             = $1ff  'vscl - important: it is assumed the upper bytes of this register are always zero (required for F16 calculation)
    
    { PeekPoke Permissions
        All other commands are always enabled.
    } 
    cEnableWriteHub         = |< 2
    cEnableSetSerialTimings = |< 5
    cEnablePayloadExec      = |< 8
    cEnableBreakDetection   = |< 15
    cEnableEverything       = $81ff

    { PeekPoke Default Settings }
    cMinReadAddr    = 0
    cMaxReadAddr    = $ffff
    cMinWriteAddr   = 0
    cMaxWriteAddr   = $ffff
    cPermissions    = cEnableEverything ^ cEnablePayloadExec

    { PeekPoke Custom Error Constants }
    cAddressForbidden   = 128


pub setPins(__rxPin, __txPin)
    rxMask := |< __rxPin
    txMask := |< __txPin
    rcvyLowCounterMode := (rcvyLowCounterMode & $ffff_ffe0) | (__rxPin & $1f)

pub setBaudrate(__baudrate)
    __twoBitPeriod := (clkfreq << 1) / __baudrate #> 52
    bitPeriod0 := __twoBitPeriod >> 1
    bitPeriod1 := bitPeriod0 + (__twoBitPeriod & 1)
    startBitWait := (bitPeriod0 >> 1) - 10 #> 5
    stopBitDuration := ((10*clkfreq) / __baudrate) - 5*bitPeriod0 - 4*bitPeriod1 + 1

pub setInterbyteTimeoutInMS(__milliseconds)
    timeout := __milliseconds*(clkfreq/1000) #> __twoBitPeriod

pub setInterbyteTimeoutInBitPeriods(__count)
    timeout := __count*bitPeriod0 #> __twoBitPeriod

pub setRecoveryTimeInMS(__milliseconds)
    recoveryTime := __milliseconds*(clkfreq/1000)

pub setRecoveryTimeInBitPeriods(__count)
    recoveryTime := __count*bitPeriod0

pub setBreakThresholdInMS(__milliseconds)
    breakMultiple := (__milliseconds*(clkfreq/1000)) / recoveryTime #> 2

pub setAddress(__address)
    _RxCheckAddress := (_RxCheckAddress & $ffff_ffe0) | (__address & $1f)

pub setPort(__port)
    _AdminOpenPortsList := (_AdminOpenPortsList & $ffff_ff00) | (__port & $ff)
    _AdminCheckUserPort := (_AdminCheckUserPort & $ffff_ff00) | (__port & $ff)
    _RxCheckUserPort := (_RxCheckUserPort & $ffff_ff00) | (__port & $ff)

pub enableWriteHub
    initPermissions |= cEnableWriteHub

pub disableWriteHub
    initPermissions &= !cEnableWriteHub

pub enableSetSerialTimings
    initPermissions |= cEnableSetSerialTimings

pub disableSetSerialTimings
    initPermissions &= !cEnableSetSerialTimings    

pub enablePayloadExec
    initPermissions |= cEnablePayloadExec

pub disablePayloadExec
    initPermissions &= !cEnablePayloadExec

pub enableBreakDetection
    initPermissions |= cEnableBreakDetection

pub disableBreakDetection
    initPermissions &= !cEnableBreakDetection

pub setReadRange(__minAddr, __maxAddr)
    minReadAddr := __minAddr
    maxReadAddr := __maxAddr
    readAddrRange := (__maxAddr << 16) | __minAddr
    
pub setWriteRange(__minAddr, __maxAddr)
    minWriteAddr := __minAddr
    maxWriteAddr := __maxAddr
    writeAddrRange := (__maxAddr << 16) | __minAddr

pub setIdentifier(__identifier)
    identifier := __identifier

pub new(__par)
    result := cognew(@Entry, __par) + 1
    waitcnt(cnt + 10000)                    'wait for cog loading to finish to protect settings of just launched cog

pub init(__cogid, __par)
    coginit(__cogid, @Entry, __par)
    waitcnt(cnt + 10000)                    'wait for cog loading to finish to protect settings of just launched cog


dat

__twoBitPeriod  long 0


{ ==========  Begin Payload Buffer, Initialization, and Entry  ========== }

{ Payload Buffer, Initialization, and Entry
    The payload buffer is where PropCR will put received payloads. It is also where it will send
  response payloads from unless sendBufferPointer is changed.
    The payload buffer is placed at the beginning of the cog for two reasons:
        - this is a good place to put one-time initialization code, and
        - having a fixed location is convenient for executing compiled code sent as a payload.
    Since the initialization code may not take up the entire buffer, shifting code is included that
  will shift the permanent code into place. This prevents wasting excessive hub space with an empty buffer.
}
org 0
Entry
Payload
                                { First, shift everything into place. Assumptions:
                                    - The actual content (not address) of the register after initEnd is initShiftStart (nothing
                                      but org and res'd registers between them).
                                    - All addresses starting from initShiftLimit and up are res'd and are not shifted. }
                                mov         _initCount, #initShiftLimit - initShiftStart
initShift                       mov         initShiftLimit-1, initShiftLimit-1-(initShiftStart - (initEnd + 1))
                                sub         initShift, initOneInDAndSFields
                                djnz        _initCount, #initShift

                                { Misc. }
                                mov         frqb, #1
                                or          outa, txMask                            'prevent glitch when retaining tx line for first time

                                { PeekPoke Initializations }

                                { Populate the reset timings. }
                                movs        _Shift, #bitPeriod0
                                movd        _Shift, #resetBitPeriod0
                                call        #ShiftSeven

                                { Enable/Disable Features }

                                test        initPermissions, #cEnableWriteHub           wc
                        if_c    movs        _JumpWriteHub, #_WriteHub
                        if_nc   movs        _JumpWriteHub, #ReportCommandNotAvailable

                                test        initPermissions, #cEnableSetSerialTimings   wc
                        if_c    movs        _JumpSetSerialTimings, #SetSerialTimings
                        if_nc   movs        _JumpSetSerialTimings, #ReportCommandNotAvailable

                                test        initPermissions, #cEnablePayloadExec        wc
                        if_c    movs        _JumpPayloadExec, #PayloadExec
                        if_nc   movs        _JumpPayloadExec, #ReportCommandNotAvailable

                                test        initPermissions, initEnableBreakDetectionFlag   wc
                        if_c    movi        _RcvyLoopJump, #%111001_001                         'djnz - counts down to break detection
                        if_nc   movi        _RcvyLoopJump, #%010111_000                         'jmp - never detects breaks

                                { Prepare the PeekPoke getInfo response. }

                                mov         parAndAvailability, initPermissions
                                shl         parAndAvailability, #16
                                or          parAndAvailability, par

                                jmp         #ReceiveCommand


initPermissions                 long    cPermissions

initEnableBreakDetectionFlag    long    |< 15

{ initEnd is the last real (not reserved) register before initShiftStart. Its address is used by the initialization shifting code. }
initEnd
initOneInDAndSFields            long    $201    'the identical constant in the permanent code can't be used since it is not yet shifted when needed


fit cNumPayloadRegisters 'On error: not enough room for init code.
org cNumPayloadRegisters


{ ==========  Begin PropCR Block  ========== }

{ initShiftStart is the first non-res'd register to be shifted into place. }
initShiftStart

{ Settings Notes
    The following registers store some settings. Some settings are stored in other locations (within
  instructions in some cases), and some are stored in multiple locations.
}
bitPeriod0              long    cBitPeriod0             'MUST be at even addressed register
bitPeriod1              long    cBitPeriod1             'MUST immediately follow bitPeriod0
startBitWait            long    cStartBitWait
stopBitDuration         long    cStopBitDuration
timeout                 long    cTimeout
recoveryTime            long    cRecoveryTime
breakMultiple           long    cBreakMultiple
rxMask                  long    |< cRxPin               'rx pin also stored in rcvyLowCounterMode
txMask                  long    |< cTxPin

ppToken                 long    0                       'must be zero at launch

kFFFF                   long    $ffff
kOneInDAndSFields       long    $201
'kOneInDField is incorporated in ppGetInfoBuffer
kFF00_0000              long    $ff00_0000 


{ ReceiveCommand (jmp)
    This routine waits for a command and then processes it in ReceiveCommandFinish. It makes use
  of instructions that are shifted into the receive loop (see 'RX Parsing Instructions' and
  'RX StartWait Instructions').
}
ReceiveCommand
                                { Pre-loop initialization. }
                                mov         _rxWait0, startBitWait                  'see page 99
                                mov         _RxStartWait, rxContinue
                                movs        _RxMovA, #rxFirstParsingGroup
                                movs        _RxMovB, #rxFirstParsingGroup+1
                                movs        _RxMovC, #rxFirstParsingGroup+2
                                mov         _rxResetOffset, #0

                                { Wait for start bit edge. }
                                waitpne     rxMask, rxMask
                                add         _rxWait0, cnt

                                { Sample start bit. }
                                waitcnt     _rxWait0, bitPeriod0
                                test        rxMask, ina                     wc      'c=1 framing error; c=0 continue, with reset
                        if_c    jmp         #RecoveryMode

                                { The receive loop -- c=0 will reset parser. }
_RxLoopTop
:bit0                           waitcnt     _rxWait0, bitPeriod1
                                testn       rxMask, ina                     wz
                        if_nc   mov         _rxF16L, #0                             'F16 1 - see page 90
                        if_c    add         _rxF16L, _rxByte                        'F16 2
                        if_c    cmpsub      _rxF16L, #255                           'F16 3
                                muxz        _rxByte, #%0000_0001

:bit1                           waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        _rxByte, #%0000_0010
                        if_nc   mov         _rxF16U_SH, #0                          'F16 4
                        if_c    add         _rxF16U_SH, _rxF16L                     'F16 5
                        if_c    cmpsub      _rxF16U_SH, #255                        'F16 6

:bit2                           waitcnt     _rxWait0, bitPeriod1
                                testn       rxMask, ina                     wz
                                muxz        _rxByte, #%0000_0100
                        if_nc   mov         _rxOffset, _rxResetOffset               'Shift 1 - see page 93
                                subs        _rxResetOffset, _rxOffset               'Shift 2
                                adds        _RxMovA, _rxOffset                      'Shift 3

:bit3                           waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        _rxByte, #%0000_1000
                                adds        _RxMovB, _rxOffset                      'Shift 4
                                adds        _RxMovC, _rxOffset                      'Shift 5
                                mov         _rxOffset, #3                           'Shift 6

:bit4                           waitcnt     _rxWait0, bitPeriod1
                                testn       rxMask, ina                     wz
                                muxz        _rxByte, #%0001_0000
_RxMovA                         mov         _RxShiftedA, 0-0                        'Shift 7
_RxMovB                         mov         _RxShiftedB, 0-0                        'Shift 8
_RxMovC                         mov         _RxShiftedC, 0-0                        'Shift 9

:bit5                           waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        _rxByte, #%0010_0000
                                mov         _rxWait1, _rxWait0                      'Wait 2
                                mov         _rxWait0, startBitWait                  'Wait 3
                                sub         _rxCountdown, #1                wz      'Countdown (undefined on reset)

:bit6                           waitcnt     _rxWait1, bitPeriod1
                                test        rxMask, ina                     wc
                                muxc        _rxByte, #%0100_0000
                        if_nc   mov         _rxCH0inc_SH, _rxByte                   'save CH0 (up through bit 6) for reserved bits testing
_RxShiftedA                     long    0-0                                         'Shift 10
                                shl         _rxLong, #8                             'Buffering 1 (_rxLong undefined on reset)

:bit7                           waitcnt     _rxWait1, bitPeriod0
                                test        rxMask, ina                     wc
                                muxc        _rxByte, #%1000_0000
                                or          _rxLong, _rxByte                        'Buffering 2
_RxShiftedB                     long    0-0                                         'Shift 11
_RxShiftedC                     long    0-0                                         'Shift 12

:stopBit                        waitcnt     _rxWait1, bitPeriod0                    'see page 98
                                testn       rxMask, ina                     wz      'z=0 framing error

_RxStartWait                    long    0-0                                         'wait for start bit, or exit loop
                        if_z    add         _rxWait0, cnt                           'Wait 1

:startBit               if_z    waitcnt     _rxWait0, bitPeriod0
                        if_z    test        rxMask, ina                     wz      'z=0 framing error
                        if_z    mov         _rxTmp_SH, _rxWait0                     'Timeout 1
                        if_z    sub         _rxTmp_SH, _rxWait1                     'Timeout 2 - see page 98 for timeout notes
                        if_z    cmp         _rxTmp_SH, timeout              wc      'Timeout 3 - c=0 reset, c=1 no reset
                        if_z    jmp         #_RxLoopTop

                        { fall through to RecoveryMode for framing errors }

{ RecoveryMode (jmp), with Break Detection 
    In recovery mode the implementation waits for the rx line to be idle for at least recoveryTime clocks, then
  it will jump to ReceiveCommand to wait for a command.
    If the rx line is continuously low for at least breakMultiple*recoveryTime clocks then a break
  condition is detected.
    RecoveryMode uses the counter B module to count the number of clocks that the rx line is low. It turns the
  counter module off before exiting since it consumes some extra power, but this is not required.
}
RecoveryMode
                                mov         ctrb, rcvyLowCounterMode                'start counter B module counting clocks the rx line is low
                                mov         _rcvyWait, recoveryTime
                                add         _rcvyWait, cnt
                                mov         _rcvyPrevPhsb, phsb                     'first wait is always recoveryTime+1 counts, so _rcvyCountdown reset guaranteed

_RcvyLoopTop                    waitcnt     _rcvyWait, recoveryTime
                                mov         _rcvyCurrPhsb, phsb
                                cmp         _rcvyPrevPhsb, _rcvyCurrPhsb    wz      'z=1 line is idle (was never low), so exit
                        if_z    mov         ctrb, #0                                'turn off counter B module
                        if_z    jmp         #ReceiveCommand
                                mov         _rcvyTmp, _rcvyPrevPhsb                 '_rcvyTmp will be value of _rcvyCurrPhsb if line always low over interval
                                add         _rcvyTmp, recoveryTime
                                cmp         _rcvyTmp, _rcvyCurrPhsb         wz      'z=0 line high at some point during interval, or this is first pass through loop
                        if_nz   mov         _rcvyCountdown, breakMultiple           'reset break detection countdown if line not continuously low
                                mov         _rcvyPrevPhsb, _rcvyCurrPhsb
_RcvyLoopJump                   djnz        _rcvyCountdown, #_RcvyLoopTop           'break detected when countdown reaches zero; init code changes to jmp to disable breaks

                                mov         ctrb, #0                                'turn off counter B module

                        { fall through to BreakHandler }

{ BreakHandler 
    When a break is detected the serial timings are reset to the last known good values.
    This code is executed immediately after the break is detected, while it may still be ongoing.
}
BreakHandler                
                                movd        _Shift, #bitPeriod0
                                movs        _Shift, #resetBitPeriod0
                                call        #ShiftSeven

                                waitpeq     rxMask, rxMask                          'wait for break to end

                                jmp         #ReceiveCommand


{ RX Parsing Instructions, used by ReceiveCommand
    There are three parsing instructions per byte received. Shifted parsing code executes inside the
  receive loop at _RxShiftedA-C. See pages 102, 97, 94.
}
rxFirstParsingGroup
rxH0                
                                xor         _rxCH0inc_SH, #1                    'A - _rxCH0inc was saved in-loop (up through bit 6); bit 0 should be 1 (invert to test)
                                test        _rxCH0inc_SH, #%0100_0111   wz      ' B - z=1 good reserved bits 0-2 and 6
                    if_nz_or_c  jmp         #RecoveryMode                       ' C - ...abort if bad reserved bits (c = bit 7 must be 0)
rxH1                            
                                shr         _rxLong, #3                         'A - prepare _rxLong to hold payloadSize (_rxLong buffering occurs between A and B)
                                mov         payloadSize, _rxLong                ' B - payloadSize still needs to be masked (upper bits undefined)
                                and         payloadSize, k7FF                   ' C - payloadSize is ready
rxH2 
                                test        _rxByte, #%0110_0000        wz      'A - test reserved bits 5 and 6 of CH2 (they must be zero)
                        if_nz   jmp         #RecoveryMode                       ' B - ...abort for bad reserved bits
                                mov         packetInfo, _rxByte                 ' C - save CH2 as packetInfo for later use
rxH3
                                mov         _rxRemaining, payloadSize           'A - _rxRemaining = number of bytes of payload yet to receive
                                mov         _rxNextAddr, #Payload               ' B - must reset _rxNextAddr before rxP* code
                                mov         _rxPort_SH, _rxByte                 ' C - save the port number
rxH4
k4143                           long    $4143                                   'A - (spacer nop) identifying bytes for Crow admin packets; potential nop
k7FF                            long    $7ff                                    ' B - (spacer nop) 2047 = maximum payload length allowed by Crow specification
                                mov         token, _rxByte                      ' C - save the token
rxF16_C0 
                                mov         _rxLeftovers, _rxLong               'A - preserve any leftover bytes in case this is the end
                                mov         _rxCountdown, _rxRemaining          ' B - _rxCountdown = number of payload bytes in next chunk
                                max         _rxCountdown, #128                  ' C - chunks have up to 128 payload bytes
rxF16_C1
                                add         _rxCountdown, #1            wz      'A - undo automatic decrement; z=1 the next chunk is empty -- i.e. done
                                sub         _rxRemaining, _rxCountdown          ' B - decrement the payload bytes remaining counter by the number in next chunk
                        if_z    mov         _RxStartWait, rxExit                ' C - z=1 no payload left, so exit
rxP0_Eval
                        if_z    subs        _rxOffset, #9                       'A - go to rxF16_C0 if done with chunk's payload
                                or          _rxF16U_SH, _rxF16L         wz      ' B - z=0 bad F16 (both F16L and F16U should be zero at this point)
                        if_nz   jmp         #RecoveryMode                       ' C - ...abort for bad F16
rxP1                    
                        if_z    subs        _rxOffset, #12                      'A - go to rxF16_C0 if done with chunk's payload
                                cmp         payloadSize, maxPayloadSize wc, wz  ' B - test for potential buffer overrun
                if_nc_and_nz    mov         _rxNextAddr, #Payload               ' C - payload too big for buffer so keep rewriting first long (will report Crow error later)
rxP2                    
                        if_z    subs        _rxOffset, #15                      'A - go to rxF16_C0 if done with chunk's payload
maxPayloadSize                  long    cMaxPayloadSize & $7ff                  ' B - (spacer nop) payloads must be 2047 or less by Crow specification
                                movd        _RxStoreLong, _rxNextAddr           ' C - prep to write next long to buffer
rxP3                    
                        if_z    subs        _rxOffset, #18                      'A - go to rxF16_C0 if done with chunk's payload
_RxStoreLong                    mov         0-0, _rxLong                        ' B
                                add         _rxNextAddr, #1                     ' C - incrementing _rxNextAddr and storing the long must occur in same block
rxP0                    
                        if_z    subs        _rxOffset, #21                      'A - go to rxF16_C0 if done with chunk's payload
                        if_nz   subs        _rxOffset, #12                      ' B - otherwise go to rxP1
rcvyLowCounterMode              long    $3000_0000 | ($1f & cRxPin)             ' C - (spacer nop) rx pin number should be set before launch


{ RX StartWait Instructions, used by ReceiveCommand
    These instructions are shifted to _RxStartWait in the receive loop to either receive more bytes or
  to exit the loop. The 'if_z' causes the instruction to be skipped if a framing error is detected on the stop bit.
}
rxContinue              if_z    waitpne     rxMask, rxMask                      'executed at _RxStartWait
rxExit                  if_z    jmp         #ReceiveCommandFinish               'executed at _RxStartWait


{ ReceiveCommandFinish 
    This is where the receive loop exits to when all bytes of the packet have arrived.
}
ReceiveCommandFinish
                                { Prepare to store any leftover (unstored) payload. This is OK even if the payload exceeds capacity. In
                                    that case _rxNextAddr will be Payload or Payload+1, and we assume there is at least two long's
                                    worth of payload capacity, so no overrun occurs. }
                                test        payloadSize, #%11               wz      'z=0 leftovers exist
                        if_nz   movd        _RxStoreLeftovers, _rxNextAddr

                                { Evaluate F16 for last byte. These are also spacer instructions that don't change z.
                                    There is no need to compute upper F16 -- it should already be 0 if there are no errors. }
                                add         _rxF16L, _rxByte
                                cmpsub      _rxF16L, #255

                                { Store the leftover payload, if any. Again, this is safe even if the command's payload
                                    exceeds capacity (see above). }
_RxStoreLeftovers       if_nz   mov         0-0, _rxLeftovers

                                { Verify the last F16. }
                                or          _rxF16U_SH, _rxF16L             wz      'z=0 bad F16
                        if_nz   jmp         #RecoveryMode                           '...bad F16 (invalid packet)

                                { Extract the address. }
                                mov         _rxTmp_SH, packetInfo
                                and         _rxTmp_SH, #cAddressMask        wz      'z=1 broadcast address; _rxTmp is now packet's address
                                test        packetInfo, #cRspExpectedFlag   wc      'c=1 response is expected/required
                    if_z_and_c  jmp         #RecoveryMode                           '...broadcast commands must not expect a response (invalid packet)

                                { At this point a valid packet has been received. It may not be addressed
                                    to this device, and it may be oversized (so its payload was not saved). }

                                { Check the address if not broadcast. }
_RxCheckAddress         if_nz   cmp         _rxTmp_SH, #cAddress            wz      'z=0 addresses don't match; address (s-field) may be set before launch
                        if_nz   jmp         #ReceiveCommand                         '...valid packet, but not addressed to this device

                                { At this point we have determined that the command was properly formatted and
                                    intended for this device (whether specifically addressed or broadcast). }

                                { Verify that the payload size was under the limit. If it exceeded capacity then the
                                    payload bytes weren't actually saved, so there's nothing to do except report
                                    that the command was too big. }
                                cmp         payloadSize, maxPayloadSize     wc, wz
                if_nc_and_nz    mov         Payload, #cOversizedCommand
                if_nc_and_nz    jmp         #SendCrowError

                                { Check the port. }
_RxCheckUserPort                cmp         _rxPort_SH, #cUserPort          wz      'z=1 command is for user code; s-field set before launch
                        if_z    jmp         #UserCode
                                cmp         _rxPort_SH, #0                  wz      'z=1 command is for Crow admin (using fall-through to save a jmp)

                                { Report that the port is not open (if not Crow admin). }
                        if_nz   mov         Payload, #cPortNotOpen
                        if_nz   jmp         #SendCrowError 

                        { fall through to CrowAdmin for port 0 }

{ CrowAdmin
    CrowAdmin starts the process of responding to standard admin commands (port 0). The admin
  code assumes that sendBufferPointer points to Payload.
    Supported admin commands: ping, echo/hostPresence, getOpenPorts, and getPortInfo.
    PeekPoke modification: getDeviceInfo removed to free registers.
}
CrowAdmin
                                { Crow admin command with no payload is ping. }
                                cmp         payloadSize, #0                 wz      'z=1 ping command
                        if_z    jmp         #SendResponse                           'the ping response also has no payload

                                { All other Crow admin commands must have at least three bytes, starting
                                    with 0x43 and 0x41. }
                                cmp         payloadSize, #3                 wc      'c=1 too few bytes
                        if_nc   mov         _admTmp, Payload
                        if_nc   and         _admTmp, kFFFF
                        if_nc   cmp         _admTmp, k4143                  wz      'z=0 bad identifying bytes
                    if_c_or_nz  jmp         #ReportUnknownCommandFormat

                                { The third byte specifies the command. }
                                mov         _admTmp, Payload
                                shr         _admTmp, #16
                                and         _admTmp, #$ff                   wz      'z=1 echo/hostPresence; masked since upper byte of Payload is unknown/undefined
                        if_z    jmp         #SendResponse
                                cmp         _admTmp, #2                     wz      'z=1 getOpenPorts
                        if_z    jmp         #AdminGetOpenPorts             
                                cmp         _admTmp, #3                     wz      'z=1 getPortInfo
                        if_nz   jmp         #ReportCommandNotAvailable

                        { fall through to AdminGetPortInfo }

{ AdminGetPortInfo (jmp)
    The getPortInfo response returns information about a specific port.
}
AdminGetPortInfo                { The port number of interest is in the fourth byte of the command. }
                                cmp         payloadSize, #4                 wc      'c=1 command too short
                        if_c    mov         Payload, #cMissingCommandData
                        if_c    jmp         #SendCrowError
                                mov         _admTmp, Payload
                                shr         _admTmp, #24                    wz      '_admTmp is the requested port number; z=1 admin port 0
                
                                { If z=1 then the requested port number is 0 (Crow admin). }
                        if_z    mov         sendBufferPointer, #getPortInfoBuffer_Admin
                        if_z    mov         payloadSize, #16
                        if_z    jmp         #SendResponseAndResetPointer

                                { Check if it is the user port. }
_AdminCheckUserPort             cmp         _admTmp, #cUserPort             wz      'z=1 user port; s-field set before launch
                        if_z    mov         sendBufferPointer, #getPortInfoBuffer_User
                        if_z    mov         payloadSize, #15
            
                                { If it is not the admin port or the user port, then the port is closed. }
                        if_nz   mov         sendBufferPointer, #getPortInfoBuffer_Closed
                        if_nz   mov         payloadSize, #4

                                jmp         #SendResponseAndResetPointer


{ AdminGetOpenPorts (jmp)
    The response consists of six bytes: 0x43, 0x41, 0x02, 0x00, plus the user port and admin port 0.
}
AdminGetOpenPorts
                                andn        Payload, kFF00_0000                     'set byte four to 0x00 (format is list of open port numbers)
_AdminOpenPortsList             mov         Payload+1, #cUserPort                   's-field set before launch (admin port 0 gets set automatically)
                                mov         payloadSize, #6

                                jmp         #SendResponse


{ The following buffers are prepared values for admin responses. If any of these buffers are changed
    remember to update the payload sizes in the above code. }

getPortInfoBuffer_Admin
long $0303_4143         'initial header (0x43, 0x41, 0x03), port is open, serviceIdentifier included
long $4309_0700         'serviceIdentifier has offset 7 and length 9; first char is "C"; final string = "CrowAdmin"
long $4177_6f72         '"rowA"
long $6e69_6d64         '"dmin"

getPortInfoBuffer_User
long $0303_4143         'initial header (0x43, 0x41, 0x03), port is open, serviceIdentifier included
long $5008_0700         'serviceIdentifier has offest 7 and length 8; first char is "P"; final string = "PeekPoke"
long $506b_6565         '"eekP"
long $0065_6b6f         '"oke"

getPortInfoBuffer_Closed
long $0003_4143         'initial header (0x43, 0x41, 0x03), port is closed, no other details 


{ TxSendAndResetF16 (call)
    Helper routine to send the current F16 checksums (upper sum, then lower sum). It also resets
  the checksums after sending.
}
TxSendAndResetF16
                                mov         _txLong, _txF16L
                                shl         _txLong, #8
                                or          _txLong, _txF16U
                                mov         _txCount, #2
                                movs        _TxHandoff, #_txLong
                                call        #TxSendBytes
                                mov         _txF16L, #0
                                mov         _txF16U, #0
TxSendAndResetF16_ret           ret


{ TxSendBytes (call)
    Helper routine used to send bytes. It also updates the running F16 checksums. It assumes
  the tx pin is already an output.
    Usage:  mov         _txCount, <number of bytes to send, MUST be non-zero>
            movs        _TxHandoff, <buffer address, sending starts with low byte>
            call        #TxSendBytes
    After: _txCount = 0                                         
}
TxSendBytes
                                mov         _txByteNum_SH, #0
                                mov         _txWait_SH, cnt
                                add         _txWait_SH, #21
_TxByteLoop                     test        _txByteNum_SH, #%11         wz          'z=1 byteNum%4 == 0, so load next long
_TxHandoff              if_z    mov         _txLong, 0-0
                        if_z    add         _TxHandoff, #1
:startBit                       waitcnt     _txWait_SH, bitPeriod0
                                andn        outa, txMask
                                mov         _txByte, _txLong
                                and         _txByte, #$ff                           '_txByte MUST be masked for F16 (also required since it aliases _rxByte)
                                add         _txF16L, _txByte
                                ror         _txLong, #1                 wc
:bit0                           waitcnt     _txWait_SH, bitPeriod1
                                muxc        outa, txMask
                                cmpsub      _txF16L, #255
                                add         _txF16U, _txF16L
                                cmpsub      _txF16U, #255
                                ror         _txLong, #1                 wc
:bit1                           waitcnt     _txWait_SH, bitPeriod0
                                muxc        outa, txMask
                                add         _txByteNum_SH, #1
                                mov         _txBitCountdown_SH, #6
:bitLoop                        ror         _txLong, #1                 wc
:bits2to7                       waitcnt     _txWait_SH, bitPeriod1
                                muxc        outa, txMask
                                xor         :bits2to7, #1                           'this is why bitPeriod0 must be at even address, with bitPeriod1 next
                                djnz        _txBitCountdown_SH, #:bitLoop
:stopBit                        waitcnt     _txWait_SH, stopBitDuration
                                or          outa, txMask
                                djnz        _txCount, #_TxByteLoop
                                waitcnt     _txWait_SH, #0                          'do not return until stop bit duration expires
TxSendBytes_ret                 ret


{ ReportUnknownCommandFormat (jmp)
    Reporting an UnknownCommandFormat error is the correct action to take if the
  received command does not conform to the expected protocol.
    After sending the error response execution goes to ReceiveCommand.
}
ReportUnknownCommandFormat
                                mov         Payload, #cUnknownCommandFormat

                            { fall through to SendCrowError }

{ SendCrowError (jmp)
    This routine sends a Crow-level error response.
    It assumes the low byte of Payload has been set to the error number.
}
SendCrowError                   or          _SendApplyTemplate, #$80                'set the error flag of the RH0 template (gets cleared at end of sending routine)
                                mov         payloadSize, #1

                            { fall through to SendResponse }

{ SendResponse (jmp), SendResponseAndReturn (call)
    Usage:  mov     payloadSize, <size of payload, in bytes, may be zero>
           (mov     sendBufferPointer, #<register of start of buffer>) 'sendBufferPointer = Payload = 0 by default; warning: admin code assumes sendBufferPointer = Payload
            jmp     #SendResponse
            -or-
            call    #SendResponseAndReturn
    After: payloadSize will be undefined. All tmp*v temporaries will also be undefined (i.e. those that alias _tx* temporaries).
}
SendResponse                    movs        Send_ret, #ReceiveCommand
SendResponseAndReturn
                                { Verify that there's an open transaction (i.e. that we are allowed to send a response). }
                                test        packetInfo, #cRspExpectedFlag       wc      'c=0 response forbidden
                        if_nc   jmp         #_SendDone                                  '...must not send if responses forbidden

                                { Make sure the payload size is within specification -- truncate if necessary. This is done to prevent
                                    sending too many payload bytes -- the payload size in the header is always masked to 11 bits. }
                                max         payloadSize, k7FF

                                { Compose header bytes RH0-RH2 in token (so RH2 already set). }
                                shl         token, #8                                   'RH2 = token
                                mov         _txCount, payloadSize                       '_txCount being used for scratch
                                and         _txCount, #$ff
                                or          token, _txCount                             'RH1 = lower eight bits of payloadSize
                                shl         token, #8
                                mov         _txCount, payloadSize
                                shr         _txCount, #5
                                and         _txCount, #%0011_1000
_SendApplyTemplate              or          _txCount, #2                                's-field is the RH0 template (sets bits other than upper three of payload size)
                                or          token, _txCount                             'RH0 = upper three bits of payloadSize, errorFlag, and reserved bits

                                { Reset F16. }
                                mov         _txF16L, #0
                                mov         _txF16U, #0

                                { Retain line (make output). }
                                or          dira, txMask

                                { Send the header (in token). }
                                mov         _txCount, #3
                                movs        _TxHandoff, #token
                                call        #TxSendBytes
                                call        #TxSendAndResetF16

                                { Send body, in chunks (payload data + F16 sums). }
                                movs        :setHandoff, sendBufferPointer
                                mov         _txRemaining, payloadSize
:loop                           mov         _txCount, _txRemaining              wz
                        if_z    jmp         #:loopExit
                                max         _txCount, #128                              'chunks are 128 bytes of payload data
                                sub         _txRemaining, _txCount
:setHandoff                     movs        _TxHandoff, #0-0
                                call        #TxSendBytes
                                call        #TxSendAndResetF16
                                add         :setHandoff, #32                            'next chunk (if any) is at +32 registers
                                jmp         #:loop

:loopExit                       { Release line (make high-z). }
                                andn        dira, txMask
                                
_SendDone                       { Clear the error flag of the RH0 template (reverts change potentially made by SendCrowError). }
                                andn        _SendApplyTemplate, #$80
Send_ret
SendResponseAndReturn_ret       ret


{ SendResponseAndResetPointer (jmp)
    This routine sends a response and then resets the sendBufferPointer to Payload before
  going to ReceiveCommand.
}
SendResponseAndResetPointer
                                call        #SendResponseAndReturn
                                mov         sendBufferPointer, #Payload
                                jmp         #ReceiveCommand


{ ==========  Begin User Block  ========== }

{ UserCode (jmp)
    This is where execution will go to when a valid command has arrived at the user port.
    Variables of interest:
        - Payload (register 0), the buffer where the command payload has been stored. Received
          data is stored in little-endian order within each long (assuming that 'propcr ordering'
          was used by the PC). If the payload size is not a multiple of four the unused upper
          bytes of the last long will be undefined.
        - payloadSize, the size of the command payload, which may be zero (this variable is also 
          used for sending).
        - packetInfo, which is the third byte of the command header. It contains the address
          in the cAddressMask bits, and the responseExpected flag in the cRspExpectedFlag bit.
        - sendBufferPointer, which points to the first register of the response payload. By 
          default it points to Payload. It may be changed, but it must be restored to Payload
          before receiving the next command (the admin code assumes it is Payload). The
          SendResponseAndResetPointer routine may be useful.
    PropCR routines for user code:
        - SendResponse (jmp), sends a response and goes to ReceiveCommand afterwards. First, prepare
          the response payload and set payloadSize. The sending routines are safe to call even
          if there is no open transaction (i.e. the responseExpected flag was not set in the
          command). In this case the sending routines silently skip sending. Sending starts
          at the low byte of sendBufferPointer and goes up from there.
        - SendResponseAndReturn (call), sends a response and then returns to the calling code.
        - SendResponseAndResetPointer (jmp), sends a response and then resets the sendBufferPointer
          to Payload before going on to ReceiveCommand.
        - ReceiveCommand (jmp) to listen for another command without sending.
        - ReportUnknownCommandFormat (jmp) to send a UnknownCommandFormat error response, indicating
          that the command's format is not known and so no other response can safely be sent.
        - SendCrowError (jmp) to send any other Crow error response, such as RequestTooLarge. Set
          the low byte of Payload to the error number before jumping. See the errors section of
          the Crow standard for an explanation of error numbers.
    Don't send more than one response. The Crow standard allows for only one response per command,
  and PropCR does not perform any checking to protect against this mistake (checking could be added
  at the cost of two instructions).
    Other useful registers:
        - tmp0-tmp4 and tmp5v-tmp9v, scratch registers available for use. The 'v' temporaries
          are undefined after a SendResponseAndReturn call. All are undefined when
          UserCode is invoked.
        - the counter A registers, which user code is entirely free to use.
        - the PAR register, which PropCR does not use (it does use the shadow register).
    Warning: don't use other SPRs without consulting the 'Special Purpose Registers' section.
}
UserCode
                                { All PeekPoke commands begin with the same four byte initial header: 
                                    0x70, 0x70, 0x00, and commandCode. If the command does not have an initial
                                    header with this format we will send a Crow-level UnknownCommandFormat error response. }
                                cmp         payloadSize, #4             wc      'c=1 payload too short
                                mov         scratch, Payload
                                andn        scratch, kFF00_0000
                                cmp         scratch, k7070              wz      'z=0 bad fixed bytes
                    if_c_or_nz  jmp         #ReportUnknownCommandFormat

                                { A PeekPoke command has been received (it may still have an invalid format), so save
                                    the serial timings. This is done here to mirror the behavior of the host implementation. }
                                movd        _Shift, #resetBitPeriod0
                                movs        _Shift, #bitPeriod0
                                call        #ShiftSeven

                                { Extract the command code and jump to the routine. }
                                mov         command, Payload
                                shr         command, #24                wz      'z=1 code = 0 (getInfo)
                        if_z    jmp         #GetInfo
                                testn       command, #%11               wz      'z=1 code = 1, 2, or 3 (hub memory commands); using fall-through
                        if_nz   max         command, #9                         '9+ will result in CommandNotAvailable error
                        if_nz   add         command, #JumpTable-4               'jump table starts at command code 4
                        if_nz   jmp         command                             'reminder: GetToken requires z=0 before jump

                        { fall through to HubMemoryCommand (z=1) }

HubMemoryCommand                { All hub memory commands have address and count (numBytes) arguments. 
                                  Hub memory commands are not allowed to wrap around the end of the hub address
                                    space. This restriction makes it easier to enforce the allowed ranges. }
                                cmp         payloadSize, #8             wc      'c=1 not enough bytes for mandatory arguments
                        if_nc   mov         address, Payload+1
                        if_nc   and         address, kFFFF
                        if_nc   mov         numBytes, Payload+1
                        if_nc   shr         numBytes, #16
                        if_nc   mov         lastAddress, address                'lastAddress will be used for verifying the range
                        if_nc   add         lastAddress, numBytes
                        if_nc   sub         lastAddress, #1
                        if_nc   cmp         kFFFF, lastAddress          wc      'c=1 command would wrap around end of hub space, which is forbidden
                        if_c    jmp         #ReportInvalidCommand 

                                { Determine the number of longs necessary to completely cover the number of bytes (there
                                    may be remainder bytes in the last long). }
                                test        numBytes, #%11              wz      'z=1 integral number of longs
                                mov         numLongs, numBytes
                                shr         numLongs, #2
                        if_nz   add         numLongs, #1

                                shr         command, #1                 wz, wc  'c=0 writeHub (2), c=1 readHub (1, so z=1) or readHubStr (3, so z=0) 
_JumpWriteHub           if_nc   jmp         #0-0                                'initializing code sets to _WriteHub or ReportCommandNotAvailable

                        { fall through to _ReadHub, where z indicates the specific command }

{ readHub (z=1), readHubStr (z=0) }
_ReadHub                        { readHub and readHubStr can request up to cMaxPayloadSize-4 bytes of data. }
                                cmp         numBytes, #cMaxPayloadSize-4+1  wc  'c=0 request too large; the +1 makes it a strict inequality test
                        if_nc   jmp         #ReportInvalidCommand

                                { Verify that the read request is within the allowed range. Assumes no wrap-around. }
                                cmp         address, minReadAddr        wc      'c=1 read starts in forbidden area
                        if_nc   cmp         maxReadAddr, lastAddress    wc      'c=1 read ends in forbidden area
                        if_c    jmp         #ReportAddressForbidden

                        if_z    movs        :nulJump, #:innerJump               'z=1 readHub, so keep going after NUL found
                        if_nz   movs        :nulJump, #SendResponse             'z=0 readHubStr, so stop after NUL found

                                movd        :clearLong, #Payload+1
                                movd        :packByte, #Payload+1
                                mov         payloadSize, #4

:outerLoop                      mov         ind, numBytes               wz      'z=1 no bytes left to write
                        if_z    jmp         #SendResponse
                                max         ind, #4
                                sub         numBytes, ind

                                mov         offset, #0

:clearLong                      mov         0-0, #0
                                add         :clearLong, kOneInDField

:innerLoop                      rdbyte      x, address                  wz      'z=1 NUL byte
                                add         address, #1
                                shl         x, offset
                                add         offset, #8
:packByte                       or          0-0, x
                                add         payloadSize, #1
:nulJump                if_z    jmp         #0-0
:innerJump                      djnz        ind, #:innerLoop

                                add         :packByte, kOneInDField

                                djnz        numLongs, #:outerLoop

                                jmp         #SendResponse


{ writeHub }
_writeHub                       { writeHub should have 8 + count bytes in the payload. Note: count may be zero. }
                                mov         scratch, #8
                                add         scratch, numBytes
                                cmp         payloadSize, scratch        wz      'z=0 wrong payload size
                        if_nz   jmp         #ReportInvalidCommand

                                { Verify that the write is within the allowed range. Assumes no wrap-around. }
                                cmp         address, minWriteAddr       wc      'c=1 write starts in forbidden area
                        if_nc   cmp         maxWriteAddr, lastAddress   wc      'c=1 write ends in forbidden area
                        if_c    jmp         #ReportAddressForbidden

                                movs        :getLong, #Payload+2
:outerLoop                      mov         ind, #4
                                max         ind, numBytes               wz      'z=1 no bytes left to write
                        if_nz   sub         numBytes, ind
:getLong                if_nz   mov         x, 0-0
                        if_nz   add         :getLong, #1
:innerLoop              if_nz   wrbyte      x, address
                        if_nz   add         address, #1
                        if_nz   ror         x, #8
                        if_nz   djnz        ind, #:innerLoop
                        if_nz   djnz        numLongs, #:outerLoop 

                                mov         payloadSize, #4
                                jmp         #SendResponse


{ Hub Memory Command Ranges
    If Spin code changes these limits then the values in the getInfo buffer will need to be changed as well.
    The endpoints are inclusive.
    Assumptions: min is always less than max, and both are in [0, $ffff].
}
minReadAddr     long    cMinReadAddr
maxReadAddr     long    cMaxReadAddr
minWriteAddr    long    cMinWriteAddr
maxWriteAddr    long    cMaxWriteAddr


{ getInfo }
GetInfo                         mov         sendBufferPointer, #ppGetInfoBuffer
                                mov         payloadSize, #30
                                jmp         #SendResponseAndResetPointer

ppGetInfoBuffer
k7070
long $0000_7070                                             'initial header for getInfo; doubles as initial header template (k7070)
long ((cMaxPayloadSize-8) << 16) | (cMaxPayloadSize-4)      'max read and write sizes determined by buffer size
readAddrRange
long (cMaxReadAddr << 16) | cMinReadAddr                    'min and max allowed read addresses; must be set by Spin code if ranges changed
writeAddrRange
long (cMaxWriteAddr << 16) | cMinWriteAddr                  'min and max allowed write addresses; must be set by Spin code if ranges changed
layoutID
long $ddcc_bbaa                                             'todo: change when layout is finalized
identifier
long 0                                                      'identifying constant set by user
parAndAvailability
long $0000_0000                                             'par and command availability bitmask are set by initializing code
kOneInDField
long $0200                                                  'the serial timings format (0) and PeekPoke version (2); doubles as kOneInDField


{ getSerialTimings }
GetSerialTimings                mov         Payload+1, #0                       'format 0 plus padding
                                movd        _Shift, #Payload+2
                                movs        _Shift, #bitPeriod0
                                call        #ShiftSeven
                                mov         payloadSize, #36
                                jmp         #SendResponse


{ setSerialTimings }
SetSerialTimings                cmp         payloadSize, #36            wz      'z=1 correct size
                         if_z   test        Payload+1, #$ff             wz      'z=1 correct format (0)
                        if_nz   jmp         #ReportInvalidCommand

                                mov         payloadSize, #4
                                call        #SendResponseAndReturn              'setting occurs after acknowledgement

                                movd        _Shift, #bitPeriod0
                                movs        _Shift, #Payload+2
                                call        #ShiftSeven

                                jmp         #ReceiveCommand

{ setToken }
SetToken                        cmp         payloadSize, #8             wz      'using z=1 to signify setToken later on
                        if_nz   jmp         #ReportInvalidCommand

                                mov         scratch, Payload+1
{ getToken, requires z=0 }
GetToken                        mov         Payload+1, ppToken
                        if_z    mov         ppToken, scratch                    'command is setToken if z=1, getToken if z=0 

                                mov         payloadSize, #8
                                jmp         #SendResponse
                                

{ payloadExec }
PayloadExec                     cmp         payloadSize, #12            wc      'c=1 payload too short
                                cmp         Payload+1, layoutID         wz      'z=0 wrong layoutID
                    if_c_or_nz  jmp         #ReportInvalidCommand
                                jmp         #Payload+2


{ JumpTable
    The jump table starts at command code 4.
    There is an implicit entry at code 9, which is not available, so the register immediately
  after the jump table must be the start of ReportCommandNotAvailable.
}
JumpTable                       jmp         #GetSerialTimings                   '4
_JumpSetSerialTimings           jmp         #0-0                                '5 - initializing code sets to SetSerialTimings or ReportCommandNotAvailable
                                jmp         #GetToken                           '6
                                jmp         #SetToken                           '7
_JumpPayloadExec                jmp         #0-0                                '8 - initializing code sets to PayloadExec or ReportCommandNotAvailable
                                
                        { 9+ not available, so next register must be start of ReportCommandNotAvailable }

{ ReportCommandNotAvailable (jmp)
}
ReportCommandNotAvailable       mov         Payload, #cCommandNotAvailable
                                jmp         #SendCrowError


{ ReportInvalidCommand (jmp)
    The catch-all error for invalid commands (wrong size, request too large).
}
ReportInvalidCommand            mov         Payload, #cInvalidCommand
                                jmp         #SendCrowError


{ ReportAddressForbidden (jmp)
    This is used specifically when a hub read or write request is not within the allowed range.
}
ReportAddressForbidden          mov         Payload, #cAddressForbidden
                                jmp         #SendCrowError


{ ShiftSeven (call)
    This helper routine shifts seven cog registers. It is used to support the serial timings commands.
} 
ShiftSeven                      mov         ind, #7
_Shift                          mov         0-0, 0-0
                                add         _Shift, kOneInDAndSFields
                                djnz        ind, #_Shift
ShiftSeven_ret                  ret


{ Possibilities for freeing registers:
    - remove echo/hostPresence (1 register); want to keep ping, getOpenPorts, and getPortInfo
    - remove serviceIdentifiers to getPortInfo responses (3 registers per service)
    - have counter B always running (3 registers)
    - use a fall-through scheme with add instructions for reporting errors (1 or 2 registers?)
    - use a single bit period (3 registers)
    - remove break detection and baudrate reversion (~16 registers)
}


{ ==========  Begin Res'd Variables and Temporaries ========== }

fit 478 'On error: must reduce user code, payload buffer, or admin code.
org 478
initShiftLimit          'The initialization shifting code will ignore registers at and above this address.

{ Reset Serial Timings
    These store the last known good serial timings.
}
resetBitPeriod0                 res     '478
resetBitPeriod1                 res     '479    
resetStartBitWait               res     '480
resetStopBitDuration            res     '481
resetTimeout                    res     '482
resetRecoveryTime               res     '483
resetBreakMultiple              res     '484

fit 485
org 485

{ Variables }
payloadSize                     res     '485 - used for both sending and receiving; potential nop; 11-bit value

{ Temporaries
    Registers 486 to 495 are reserved for temporaries. These are temporary (aka local or scratch) variables used
  by PropCR. User code may also use these registers. The temporaries ending with a "v" will be undefined after
  SendResponseAndReturn. All of these will be undefined immediately after a command is received.
    Some variables and temporaries are stored in special purpose registers -- see 'Special Purpose Registers'.
}
fit 486
org 486

{ The following five temporaries -- registers 486 to 490 -- preserve their values during a SendResponseAndReturn call. }

scratch
tmp0
_rxWait0        res     '486

x
tmp1
_rxWait1        res     '487

y
tmp2
_rxResetOffset  res     '488

ind
tmp3
_rxOffset       res     '489

offset
tmp4
_rxNextAddr     res     '490

{ The following five "v" temporaries -- registers 491 to 495 -- are undefined after a SendResponseAndReturn call. }

address
tmp5v
_rcvyPrevPhsb
_txF16L
_rxF16L         res     '491

numBytes
tmp6v
_rcvyCurrPhsb
_txLong
_rxLong         res     '492

numLongs
tmp7v
_rcvyWait
_txF16U
_rxLeftovers    res     '493

command
tmp8v
_initTmp
_rcvyTmp
_txRemaining
_rxRemaining    res     '494

lastAddress
tmp9v
_initCount
_admTmp
_rcvyCountdown
_txCount
_rxCountdown    res     '495

fit 496



