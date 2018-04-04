{
======================================
PeekPoke
Version 2 - in development
April 2018
Chris Siedell
http://siedell.com/projects/PeekPoke/
======================================

PeekPoke is a tool for manipulating the hub RAM from a PC. This implementation is built
using PropCR-Fast v0.1.

This version is cog-contained, and does not require any hub space for data or code after
initialization. It supports the writeBytes, writeLongs, and readLongs commands.

Usage: in spin, call setParams(), then init() or new().

"PeekPoke v1.txt" describes the protocol.
}


con

{ conNumPayloadRegisters determines the size of the payload buffer. This buffer is where PropCR
    puts received command payloads. It is also where PropCR sends response payloads from unless
    sendBufferPointer is changed (by default it points to Payload).
 Due to the requirement that bitPeriod0 must be at an even-addressed register this number must
    be even, otherwise transmitting will fail with weird looking framing errors. }

'PeekPoke: 130 = 520 bytes = 512 bytes data and 8 bytes header
conNumPayloadRegisters  = 130       'Important: this MUST be an even number.

{ conUserProtocol identifies the user protocol number that PropCR will listen for. This number must
    match the protocol number sent with user commands from the PC. }

'PeekPoke: $AFAF = complement of $5050 ("PP")
conUserProtocol         = $AFAF     'Must be two byte value.

'These constants are used in the code.
conMuteFlag             = %0100_0000
conAddressMask          = %0001_1111
conMaxPayloadLength     = 4*conNumPayloadRegisters

'These are the PeekPoke error codes:
UnsupportedCommand  = 1
MissingArguments    = 2
InvalidArgument     = 3
RangeError          = 4

{ These bitmasks determine which commands are availabled. }
cImplementedGroups  = %1001
cAllowedGroups      = %1111

{ PeekPoke error numbers. }
cNotAvailable       = 0
cNotAllowed         = 1
cNotImplemented     = 2
cMissingArguments   = 3
cInvalidArguments   = 4
cUnknownCommand     = 5


var

    long    __params[8]


{
setParams(rxPin, txPin, baudrate, address)
Call before init() or new().
Parameters:
    rxPin, txPin - the sending and receiving pins, which may be the same pin
    baudrate - desired baudrate (e.g. 115200, 3_000_000)
    address - device address (must be 1-31); commands must be sent to this address if not broadcast
}
pub setParams(__rxPin, __txPin, __baudrate, __address) | __tmp
    
    __tmp := ( 2 * clkfreq ) / __baudrate       '__tmp is now 2 bit periods, in clocks
    
    __params[0] := __tmp >> 1                                                           'bitPeriod0
    __params[1] := __params[0] + (__tmp & 1)                                            'bitPeriod1 = bitPeriod0 + [0 or 1]
    __params[2] := (__params[0] >> 1) - 10 #> 5                                         'startBitWait (an offset used for receiving)
    __params[3] := ((10*clkfreq) / __baudrate) - 5*__params[0] - 4*__params[1] + 1 + 2*__params[0]     'stopBitDuration (for sending; add extra bit period if required)
    
    __tmp <<= 3                                 '__tmp is now 16 bit periods, in clocks
    
    __params[4] := __tmp                                                                'timeout, in clocks; see "The Interbyte Timeout" in User Guide
    
    'The default 16 bit period timeout above is based on the assumption that the PC's command 
    ' packet will be received in a steady stream, with no pauses between bytes. If this assumption
    ' is not true then the timeout may be defined in milliseconds, as shown below.
    'See "The Interbyte Timeout" section of the User Guide for more details.
    '__params[4] := (clkfreq/1000) * <non-zero number of milliseconds>    'timeout set using milliseconds
    
    __params[5] := __tmp                                                                'recoveryTime (in clocks; see "Recovery Mode" in User Guide)
    __params.byte[24] := __txPin
    __params.byte[25] := __rxPin
    __params.byte[26] := __address


{
new()
Call setParams() first.
Starts an instance using cognew. Calls to setParams() have no effect after this call.
}
pub new(newPar)
    
    __params.word[14] := newPar
    cognew(@Payload, @__params)
    waitcnt(cnt + 10000)            'wait for cog to load params


{
init(id)
Call setParams() first.
Starts an instance using coginit and the provided cog ID. Calls to setParams() have no effect
after this call.
}
pub init(__id) 
    
    coginit(__id, @Payload, @__params)
    waitcnt(cnt + 10000)            'wait for cog to load params


dat
org 0


{ ==========  Begin Payload Buffer and Initialization  ========== }


Payload
                                { First, shift everything starting from ReceiveCommand and up into place. 
                                    This is done so that having the payload buffer at the start of the
                                    cog doesn't waste excessive hub space. Assumptions:
                                    - initEnd+1 contains the first unshifted instruction of ReceiveCommand.
                                    - All addresses starting from initShiftLimit and up are res'd
                                      and are not shifted. }
                                mov         inb, #initShiftLimit - ReceiveCommand
initShift                       mov         initShiftLimit-1, initShiftLimit-1-(ReceiveCommand - (initEnd + 1))
                                sub         initShift, initOneInDAndSFields
                                djnz        inb, #initShift

                                { Get settings from hub. }
                                mov         _initHub, par

                                { The first six settings can be stored via loop. }
                                mov         inb, #6
initHubLoop                     rdlong      bitPeriod0, _initHub
                                add         initHubLoop, initOneInDField
                                add         _initHub, #4
                                djnz        inb, #initHubLoop

                                { Most of the remaining settings will require processing. }
                                rdbyte      _initTxPin, _initHub
                                add         _initHub, #1
                                rdbyte      _initRxPin, _initHub
                                add         _initHub, #1
                                rdbyte      _initDeviceAddress, _initHub

                                { ctrb setup - used in recovery mode }
                                movs        rcvyLowCounterMode, _initRxPin
                                mov         frqb, #1

                                { rx mask }
                                mov         rxMask, #1
                                shl         rxMask, _initRxPin

                                { tx mask }
                                mov         txMask, #1
                                shl         txMask, _initTxPin
                                or          outa, txMask            'must occur before making tx an output

                                { device address }
                                movs        rxVerifyAddress, _initDeviceAddress

                                jmp         #ReceiveCommand

initOneInDAndSFields            long    $201

{ initEnd is the last real (not reserved) register before the first unshifted register of the
    ReceiveCommand routine. Its address is used by the initialization shifting code. }
initEnd
initOneInDField                 long    $200


fit conNumPayloadRegisters      'If this fails then the payload buffer is too small for the initialization code.
org conNumPayloadRegisters


{ ==========  Begin PropCR Block  ========== }


{ Settings }
{ It is almost always an error to have res'd symbols before real instructions or data, but
    in this case it is correct -- the shifting code at the beginning takes it into account. }
bitPeriod0              res     'bitPeriod0 must be at even address (see txBitX)
bitPeriod1              res     'bitPeriod1 must immediately follow bitPeriod0
startBitWait            res
stopBitDuration         res
timeout                 res
recoveryTime            res
                                'userProtocol stored as nop elsewhere (set at compile time)
                                'userProtocol also stored in byte swapped form in adminGetDeviceInfoBuffer
txMask                  res
rxMask                  res     'rx pin number also stored in s-field of rcvyLowCounterMode
                                'deviceAddress stored in s-field of rxVerifyAddress


{ Other Res'd Variables }
token                   res     'potential nop; one byte value
packetInfo              res     'potential nop; upper bytes always set to 0
payloadLength           res     'potential nop; 11 bit value


{ Receive Command 1 - Start }
{ The first instruction of ReceiveCommand must occupy the register at initEnd+1 (before shifting),
    so there must be nothing but res'd symbols in between. }
ReceiveCommand
                                mov         _rxWait0, startBitWait                  'see page 99
                                mov         rxStartWait, rxContinue
                                movs        rxMovA, #rxH0
                                movs        rxMovB, #rxH0+1
                                movs        rxMovC, #rxH0+2
                                mov         _rxResetOffset, #0
                                waitpne     rxMask, rxMask
                                add         _rxWait0, cnt
                                waitcnt     _rxWait0, bitPeriod0
                                test        rxMask, ina                     wc      'c=1 framing error; c=0 continue, with reset
                        if_c    jmp         #RecoveryMode
                                { the receive loop - c=0 reset parser}
rxBit0                          waitcnt     _rxWait0, bitPeriod1
                                testn       rxMask, ina                     wz
                        if_nc   mov         _rxF16L, #0                             'F16 1 - see page 90
                        if_c    add         _rxF16L, rxByte                         'F16 2
                        if_c    cmpsub      _rxF16L, #255                           'F16 3
                                muxz        rxByte, #%0000_0001
rxBit1                          waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        rxByte, #%0000_0010
                        if_nc   mov         inb, #0                                 'F16 4 - inb is upper rxF16
                        if_c    add         inb, _rxF16L                            'F16 5
                        if_c    cmpsub      inb, #255                               'F16 6
rxBit2                          waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        rxByte, #%0000_0100
                        if_nc   mov         _rxOffset, _rxResetOffset               'Shift 1 - see page 93
                                subs        _rxResetOffset, _rxOffset               'Shift 2
                                adds        rxMovA, _rxOffset                       'Shift 3
rxBit3                          waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        rxByte, #%0000_1000
                                adds        rxMovB, _rxOffset                       'Shift 4
                                adds        rxMovC, _rxOffset                       'Shift 5
                                mov         _rxOffset, #3                           'Shift 6
rxBit4                          waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        rxByte, #%0001_0000
rxMovA                          mov         rxShiftedA, 0-0                         'Shift 7
rxMovB                          mov         rxShiftedB, 0-0                         'Shift 8
rxMovC                          mov         rxShiftedC, 0-0                         'Shift 9
rxBit5                          waitcnt     _rxWait0, bitPeriod0
                                testn       rxMask, ina                     wz
                                muxz        rxByte, #%0010_0000
                                mov         _rxWait1, _rxWait0                      'Wait 2
                                mov         _rxWait0, startBitWait                  'Wait 3
                        if_nc   mov         _rxCountdown, #511                      'Countdown 1
rxBit6                          waitcnt     _rxWait1, bitPeriod1
                                test        rxMask, ina                     wc
                                muxc        rxByte, #%0100_0000
                                sub         _rxCountdown, #1                wz      'Countdown 2
rxShiftedA                      long    0-0                                         'Shift 10
                                shl         _rxLong, #8                             'Buffering 1
rxBit7                          waitcnt     _rxWait1, bitPeriod0
                                test        rxMask, ina                     wc
                                muxc        rxByte, #%1000_0000
                                or          _rxLong, rxByte                         'Buffering 2
rxShiftedB                      long    0-0                                         'Shift 11
rxShiftedC                      long    0-0                                         'Shift 12
rxStopBit                       waitcnt     _rxWait1, bitPeriod0                    'see page 98
                                testn       rxMask, ina                     wz      'z=0 framing error
rxStartWait                     long    0-0                                         'wait for start bit, or exit loop
                        if_z    add         _rxWait0, cnt                           'Wait 1
rxStartBit              if_z    waitcnt     _rxWait0, bitPeriod0
                        if_z    test        rxMask, ina                     wz      'z=0 framing error
                        if_z    mov         phsb, _rxWait0                          'Timeout 1 - phsb used as scratch since ctrb should be off
                        if_z    sub         phsb, _rxWait1                          'Timeout 2 - see page 98 for timeout notes
                        if_z    cmp         phsb, timeout                    wc     'Timeout 3 - c=0 reset, c=1 no reset
                        if_z    jmp         #rxBit0

                    { fall through to recovery mode for framing errors }

{ Recovery Mode }
RecoveryMode
                                mov         ctrb, rcvyLowCounterMode
                                mov         cnt, recoveryTime
                                add         cnt, cnt
                                mov         _rcvyPrevPhsb, phsb
rcvyLoop                        waitcnt     cnt, recoveryTime
                                mov         _rcvyCurrPhsb, phsb
                                cmp         _rcvyPrevPhsb, _rcvyCurrPhsb    wz      'z=1 line always high, so exit
                        if_z    mov         ctrb, #0                                'ctrb must be off before exit
                        if_z    jmp         #ReceiveCommand
                                mov         _rcvyPrevPhsb, _rcvyCurrPhsb
                                jmp         #rcvyLoop


{ Receive Command 2 - Finishing Up After Packet Arrival }
ReceiveCommand2
                                { prepare to store any leftover payload }
                                test        payloadLength, #%11             wz      'z=0 leftovers exist
                        if_nz   movd        rxStoreLeftovers, _rxNextAddr
                                { evaluate F16 for last byte; these are also spacer instructions that don't change z;
                                    no need to compute upper F16, it should already be 0 if there are no errors }
                                add         _rxF16L, rxByte
                                cmpsub      _rxF16L, #255
                                { store the leftover payload, if any }
rxStoreLeftovers        if_nz   mov         0-0, _rxLeftovers
                                { verify the last F16 }
                                or          inb, _rxF16L                    wz      'z=0 bad F16; inb is upper rxF16
                        if_nz   jmp         #RecoveryMode                           '...bad F16 (invalid packet)
                                { verify reserved bit 5 of CH3 }
                                test        packetInfo, #%0010_0000         wc      'c=1 bad bit 5 (must be 0); packetInfo=CH3 from rxH3
                        if_c    jmp         #RecoveryMode                           '...bad reserved bit 5 of CH3 (invalid packet)
                                { finish parsing address and verify it }
                                and         cnt, #conAddressMask            wz      'z=1 broadcast address; cnt is now packet's address (originally from rxH3)
                                test        packetInfo, #conMuteFlag        wc      'c=1 mute response
                    if_z_and_nc jmp         #RecoveryMode                           '...broadcast must mute (invalid packet)
                                { verify address if not broadcast }
rxVerifyAddress         if_nz   cmp         cnt, #0-0                       wz      'cnt is packet's address (from above); device address (s-field) set at initialization
                        if_nz   jmp         #ReceiveCommand                         '...wrong non-broadcast address
                                { test command type and protocol }
                                test        ina, #%0001_0000                wc      'c=1 user command; ina=CH0 from rxH0
                                cmp         par, userProtocol               wz      'z=0 protocol doesn't match user protocol; par is packet's protocol (from rxH2 or rxH5)
                    if_c_and_nz jmp         #ReceiveCommand                         '...wrong protocol for user command
                        if_c    jmp         #UserCode                               '...valid user command with correct protocol, so invoke user code

                            { fall through to admin code }

{ Admin Code }
{ Admin code handles responses to admin commands, such as ping and getDeviceInfo. Admin code must 
    always save and restore sendBufferPointer so that user code can assume it doesn't change.
  At this point the admin protocol number has not been checked to see if it's supported. }
AdminCode                       cmp         par, #0                         wz      'z=1 universal admin protocol (=0); par is packet's protocol (from rxH2 or rxH5)
                        if_nz   jmp         #ReceiveCommand                         '...not admin protocol 0 (so unsupported admin protocol)
                                test        packetInfo, #conMuteFlag        wc      'c=1 muted response (and possible broadcast command)
                        if_c    jmp         #RecoveryMode                           '...admin protocol 0 commands must not be muted or broadcast (invalid command)
                                { admin protocol 0 with no payload is ping }
                                cmp         payloadLength, #0               wz      'z=1 ping command
                        if_nz   jmp         #adminCheckForGetDeviceInfo             '...command not ping
                                { perform ping - params all ready (no payload, so sendBufferPointer not used }
                                jmp         #SendFinalResponse
                                { other admin protocol 0 command, getDeviceInfo, has 0x00 as payload }
adminCheckForGetDeviceInfo      cmp         payloadLength, #1               wz      'z=0 wrong payload length for getDeviceInfo
                        if_z    test        Payload, #$ff                   wz      'z=0 wrong payload for getDeviceInfo
                        if_nz   jmp         #RecoveryMode                           '...command not getDeviceInfo or ping, so invalid for admin protocol 0
                                { perform getDeviceInfo }
                                mov         _adminTmp, sendBufferPointer            'save sendBufferPointer
                                mov         sendBufferPointer, #adminGetDeviceInfoBuffer
                                mov         payloadLength, #12
                                call        #SendFinalAndReturn
                                mov         sendBufferPointer, _adminTmp            'restore sendBufferPointer
                                jmp         #ReceiveCommand

{ This is the prepared getDeviceInfo response payload. }
adminGetDeviceInfoBuffer
    long    $51800100                                                                               'Crow v1, implementationID = $8051 (PropCR-Fast-BD)
    long    $01010000 | ((conMaxPayloadLength & $ff) << 8) | ((conMaxPayloadLength & $700) >> 8)    'conMaxPayloadLength, supports 1 admin protocol and 1 user protocol
    long    ((conUserProtocol & $ff) << 24) | ((conUserProtocol & $ff00) << 8)                      'admin protocol 0, conUserProtocol


{ Receive Command 3 - Shifted Code }
{ There are three parsing instructions per byte received. Shifted parsing code executes inside the
    receive loop at rxShiftedA-C. See pages 102, 97, 94. }
rxH0                    if_c    test        rxByte, #%0010_1000         wz      'A - z=1 good reserved bits 3, 5, and 6 (z=0 before due to countdown reset)
                    if_nz_or_c  jmp         #RecoveryMode                       ' B - ...abort if bad reserved bits (bit 7 must be 0); might be another device's response
                                mov         ina, rxByte                         ' C - ina used to save the T field (command type)
rxH1                            and         _rxLong, #$7                        'A - mask off upper three bits for payloadLength (shift occurs between A and B)
                                mov         payloadLength, _rxLong              ' B
                                mov         _rxRemaining, payloadLength         ' C - _rxRemaining = number of bytes of payload yet to receive
rxH2                            mov         par, #0                             'A - par used to hold packet's protocol; must set implicit 0 value
                                mov         _rxNextAddr, #Payload               ' B - must reset _rxNextAddr before rxP* code
                                mov         token, rxByte                       ' C
rxH3                            mov         cnt, rxByte                         'A - cnt used to hold packet's address; used in ReceiveCommand2
                                mov         packetInfo, rxByte                  ' B
                        if_nc   mov         _rxOffset, #9                       ' C
rxH4
rcvyLowCounterMode              long    $3000_0000                              'A - required nop - rx pin number set in initialization
kFFFF                           long    $ffff                                   ' B - required nop
k7FF                            long    $7FF                                    ' C - required nop; 2047 = maximum payload length allowed by Crow specification
rxH5
maxPayloadLength                long    conMaxPayloadLength & $7ff              'A - required nop - must be 2047 or less by Crow specification
                                mov         par, _rxLong                        ' B - reminder: par is packet's protocol
                                and         par, kFFFF                          ' C
rxF16C0                         mov         _rxLeftovers, _rxLong               'A - store any leftover bytes in case this is the end
                                mov         _rxCountdown, _rxRemaining          ' B
                                max         _rxCountdown, #128                  ' C - _rxCountdown = number of payload bytes in next chunk
rxF16C1                         add         _rxCountdown, #1            wz      'A - undo automatic decrement
                                sub         _rxRemaining, _rxCountdown          ' B
                        if_z    mov         rxStartWait, rxExit                 ' C - no payload left, so exit
rxP0Eval                if_z    subs        _rxOffset, #9                       'A - go to rxF16C0 if done with chunk's payload
                                or          inb, _rxF16L                wz      ' B - z=0 bad F16 - inb is upper rxF16
                        if_nz   jmp         #RecoveryMode                       ' C - ...bad F16
rxP1                    if_z    subs        _rxOffset, #12                              'A - go to rxF16C0 if done with chunk's payload
                                cmp         payloadLength, maxPayloadLength     wc, wz  ' B
                if_nc_and_nz    jmp         #RecoveryMode                               ' C - ...payload too big for buffer
rxP2                    if_z    subs        _rxOffset, #15                      'A - go to rxF16C0 if done with chunk's payload
txByte
rxByte                          long    0                                       ' B - required nop - upper bytes must always be 0 for F16
                                movd        rxStoreLong, _rxNextAddr            ' C
rxP3                    if_z    subs        _rxOffset, #18                      'A - go to rxF16C0 if done with chunk's payload
                                add         _rxNextAddr, #1                     ' B - incrementing _rxNextAddr and storing the long must occur in same block
rxStoreLong                     mov         0-0, _rxLong                        ' C
rxP0                    if_z    subs        _rxOffset, #21                      'A - go to rxF16C0 if done with chunk's payload
                        if_nz   subs        _rxOffset, #12                      ' B - otherwise go to rxP1
userProtocol                    long    conUserProtocol & $ffff                 ' C - required nop

rxContinue              if_z    waitpne     rxMask, rxMask                  'executed at rxStartWait
rxExit                  if_z    jmp         #ReceiveCommand2                'executed at rxStartWait


{ txSendAndResetF16 }
{ Helper routine to send the current F16 checksum (upper sum, then lower sum). It also resets
    the checksum after sending. }
txSendAndResetF16
                                mov         _txLong, _txF16L
                                shl         _txLong, #8
                                or          _txLong, _txF16U
                                mov         _txCount, #2
                                movs        txHandoff, #_txLong
                                call        #txSendBytes
                                mov         _txF16L, #0
                                mov         _txF16U, #0
txSendAndResetF16_ret           ret


{ txSendBytes }
{ Helper routine used to send bytes. It also updates the running F16 checksum. It assumes
    the tx pin is already an output.
  Usage:    mov         _txCount, <number to send != 0>
            movs        txHandoff, #<buffer register>   (no # if using pointer)
            call        #txSendBytes                                                }
txSendBytes
                                mov         par, #0                                 'par used to perform handoff every 4 bytes
                                mov         cnt, cnt                                'cnt used for timing
                                add         cnt, #21
txByteLoop                      test        par, #%11                   wz
txHandoff               if_z    mov         _txLong, 0-0
                        if_z    add         txHandoff, #1
txStartBit                      waitcnt     cnt, bitPeriod0
                                andn        outa, txMask
                                mov         txByte, _txLong
                                and         txByte, #$ff                            'txByte MUST be masked for F16 (also is a nop)
                                add         _txF16L, txByte
                                ror         _txLong, #1                 wc
txBit0                          waitcnt     cnt, bitPeriod1
                                muxc        outa, txMask
                                cmpsub      _txF16L, #255
                                add         _txF16U, _txF16L
                                cmpsub      _txF16U, #255
                                ror         _txLong, #1                 wc
txBit1                          waitcnt     cnt, bitPeriod0
                                muxc        outa, txMask
                                add         par, #1
                                mov         inb, #6                                 'inb is bit loop count
txBitLoop                       ror         _txLong, #1                 wc
txBitX                          waitcnt     cnt, bitPeriod1
                                muxc        outa, txMask
                                xor         txBitX, #1                              'this is why bitPeriod0 must be at even address, with bitPeriod1 next
                                djnz        inb, #txBitLoop
txStopBit                       waitcnt     cnt, stopBitDuration
                                or          outa, txMask
                                djnz        _txCount, #txByteLoop
                                waitcnt     cnt, #0
txSendBytes_ret                 ret


{ Sending Routines: SendFinalResponse (jmp)
                    SendFinalAndReturn (call) }
SendFinalResponse
                                movs        Send_ret, #ReceiveCommand
SendFinalAndReturn
                                { check if muted, and ensure payload length is within specification limits }
txPerformChecks                 test        packetInfo, #conMuteFlag            wc      'c=1 muted
                        if_c    jmp         Send_ret                                    '...must not send anything if responses muted
                                max         payloadLength, k7FF                         'must not exceed specification max
                                { compose header bytes RH0-RH2 }
                                mov         _txLong, token
                                shl         _txLong, #8
                                mov         _txCount, payloadLength                     '_txCount being used as a scratch register for next 8 instructions
                                and         _txCount, #$ff
                                or          _txLong, _txCount
                                shl         _txLong, #8
                                mov         _txCount, payloadLength
                                shr         _txCount, #8
                                or          _txCount, #$90                              'apply header template 
                                or          _txLong, _txCount
                                { reset F16 }
                                mov         _txF16L, #0
                                mov         _txF16U, #0
                                { send header }
                                mov         _txCount, #3
                                movs        txHandoff, #_txLong
txRetainLine                    or          dira, txMask
                                call        #txSendBytes
                                call        #txSendAndResetF16
                                { send body, in chunks (payload data + F16 sums) }
                                movs        txSetHandoff, sendBufferPointer
                                mov         _txRemaining, payloadLength
txPayloadLoop                   mov         _txCount, _txRemaining              wz
                        if_z    jmp         #txLoopExit
                                max         _txCount, #128                              'chunks are 128 bytes of payload data
                                sub         _txRemaining, _txCount
txSetHandoff                    movs        txHandoff, #0-0
                                call        #txSendBytes
                                call        #txSendAndResetF16
                                add         txSetHandoff, #32                           'next chunk (if any) is at +32 registers
                                jmp         #txPayloadLoop
txLoopExit
txReleaseLine                   andn        dira, txMask
Send_ret
SendFinalAndReturn_ret          ret

sendBufferPointer       long    Payload     'potential nop if only lower 9 bits set


{ ==========  Begin User Block  ========== }


{ User Code }
{ This is where PropCR code will jmp to when a valid user command packet has arrived.
  Refer to "PropCR-Fast User Guide.txt" for more information. }
UserCode
                                { All PeekPoke commands begin with at least four bytes of payload with the same format:
                                    0x50, 0x70, code -- where code is a two-byte value in little-endian order. The
                                    code's top bit must be 0. }
                                cmp         payloadLength, #4           wc      'c=1 payload too short
                        if_nc   mov         tmp1, Payload                       'tmp1 being used for scratch to test initial two bytes
                        if_nc   shl         tmp1, #1                    wc, nr  'c=1 bad top bit
                        if_nc   and         tmp1, kFFFF
                        if_nc   cmp         tmp1, k7050                 wz      'z=0 wrong initial header bytes
                    if_c_or_nz  jmp         #ReceiveCommand                     '...exit -- bad command initial header

                                { After this point we assume the payload is a PeekPoke command. The response payload
                                    will have the same initial four bytes as the command payload. }

                                { Extract the command code and see if that group is available (implemented and allowed). }
                                mov         tmp0, Payload
                                shr         tmp0, #16                           'tmp0 is command code
                                mov         tmp1, #1
                                shl         tmp1, tmp0                          'bottom 5 bits of code determine group
                                test        tmp1, availableGroups       wc      'c=1 command is implemented and allowed
                        if_nc   mov         errorCode, #cNotAvailable
                        if_nc   jmp         #SendErrorResponse

                                shr         tmp0, #5                    wz      'tmp0 is now command sub-group; z=1 sub-group is zero

                                test        tmp1, #%0001                wc      'c=1 getBasicInfo()
                        if_c    jmp         #GetBasicInfo

                                test        tmp1, #%0110                wc      'c=1 readHub/writeHub
                        if_c    jmp         #HubReadWrite

                                test        tmp1, #%1000                wc      'c=1 cog control
                        if_c    jmp         #CogControl

                                { This shouldn't happen. }
                                jmp         #ReceiveCommand


GetBasicInfo                    { The getBasicInfo response has the following format (all little-endian):
                                    0-3     - same as command
                                    4-5     - par
                                    6       - cogID
                                    7       - 0x00
                                    8-11    - availableGroups }
                                cogid       Payload+1
                                shl         Payload+1, #16
                                mov         tmp0, par
                                add         tmp0, #28
                                rdword      tmp0, tmp0
                                or          Payload+1, tmp0                 'todo: stop faking par
                                mov         Payload+2, availableGroups
                                mov         payloadLength, #12
                                jmp         #SendFinalResponse


HubReadWrite
                                jmp         #ReceiveCommand




CogControl  
                        if_z    jmp         #_PasmCogInit                       'z from before jump (z=1 => tmp0==0)
                                cmp         tmp0, #1                    wz      'z=1 cogStop
                        if_z    jmp         #_CogStop
                                mov         errorCode, #cUnknownCommand
                                jmp         #SendErrorResponse

_PasmCogInit
                                { pasmCogInit command has 4 additional bytes which provide the information required
                                    by the coginit instruction. The return payload has five bytes:
                                    0-3     - same as command
                                    4       - cogID as written by coginit in lower bits, c-flag in bit 7 }
                                cmp         payloadLength, #8           wc
                        if_c    mov         errorCode, #cMissingArguments
                        if_c    jmp         #SendErrorResponse
                                coginit     Payload+1                   wc, wr  'c=1 no cog available
                                jmp         #_CogControlDone

_CogStop
                                { cogStop has one additional byte -- the id of the cog to stop. The return payload has
                                    five bytes:
                                    0-3     - same as command
                                    4       - cogID of cog stopped in lower bits, c-flag in bit 7 }
                                cmp         payloadLength, #1           wc
                        if_c    mov         errorCode, #cMissingArguments
                        if_c    jmp         #SendErrorResponse
                                cogstop     Payload+1                   wc, wr  'c=1 all cogs were running

_CogControlDone                 muxc        Payload+1, #%1000_0000
                                mov         payloadLength, #5
                                jmp         #SendFinalResponse 
                                
{ *** }
'
'                                { response header (Payload register) is now ready; error responses
'                                  will just need to set error bit and or-in the error code (or
'                                  leave byte 3 at 0 for UnspecifiedError) }
'
'                                { send error response if previous reserved bits test failed,
'                                  the z flag should be unchanged from that test }
'                        if_nz   mov         errorCode, #UnsupportedCommand      '...reserved bits not zero (so unsupported command)
'                        if_nz   jmp         #SendErrorResponse
'
'                                { the actions in v1 -- reading and writing -- require eight
'                                  bytes for the header}
'                                cmp         payloadLength, #8           wc
'                        if_c    mov         errorCode, #MissingArguments        '...insufficient payload for arguments
'                        if_c    jmp         #SendErrorResponse
'
'                                { parse byte 2 (details) 
'                                  the T and A fields should still be the same after preparing
'                                  the response header }
'                                mov         dataType, Payload
'                                shr         dataType, #16
'                                and         dataType, #%11              wc, wz
'                if_nc_and_nz    mov         errorCode, #UnsupportedCommand      '...T field = 3 is not supported
'                if_nc_and_nz    jmp         #SendErrorResponse
'                                mov         par, Payload
'                                shr         par, #18                            'bit 2 of byte 2 is A field (action)
'                                and         par, #1                     wc      'c=1 write, c=0 read
'
'                                { get the address argument }
'                                mov         address, Payload+1
'                                and         address, kFFFF
'
'                                { get the count argument }
'                                mov         count, Payload+1
'                                shr         count, #16
'                                add         count, #1                           'argument in header is actually count minus one
'                                                                                'count guaranteed to be 1 to 65536 by program logic
'
'                                { prepare to verify count -- determine request size in bytes }
'                                mov         bytesRequested, count
'                                shl         bytesRequested, dataType
'
'                                { verifying count depends on action }
'                        if_c    jmp         #PerformWrite
'
'                            { fall through to PerformRead }
'
'{ Perform Read
'  We still need to verify that the count request, in bytes, is less than the 2^16 limit. }
'PerformRead
'                                { verify count -- i.e. request is less than or equal to hub size }
'                                cmp         bytesRequested, k10000      wc, wz
'                if_nc_and_nz    mov         errorCode, #RangeError              '...request exceeds hub size
'                if_nc_and_nz    jmp         #SendErrorResponse
'                                { verify that data section for read command is empty }
'                                cmp         payloadLength, #8           wz
'                        if_nz   mov         errorCode, #InvalidArgument         '...the data section of read command must be empty
'                        if_nz   jmp         #SendErrorResponse
'
'                                { at this point the header has been parsed and verified,
'                                  what happens next depends on the data type }
'                                cmp         dataType, #2                wz
'                        if_z    jmp         #ReadLongs
'
'                                { only readLongs implemented at this time }
'                                mov         errorCode, #UnsupportedCommand      '...readBytes and readWords unimplemented
'                                jmp         #SendErrorResponse
'
'ReadLongs
':outerLoop                      movd        :innerLoop, #Payload+1
'                                mov         rdInnerCount, count                 'count guaranteed initially non-zero by program logic
'                                max         rdInnerCount, #128
'                                sub         count, rdInnerCount         wz
'
'                                { prepare payloadLength for response }
'                                mov         payloadLength, rdInnerCount
'                                shl         payloadLength, #2
'                                add         payloadLength, #4
'
':innerLoop                      rdlong      0-0, address
'                                add         address, #4
'                                add         :innerLoop, kOneInDField
'                                djnz        rdInnerCount, #:innerLoop
'
'                                { nothing left to send after this if z = 1 }
'                        if_z    jmp         #SendFinalResponse
'
'                                call        #SendIntermediate
'
'                                add         Payload, kOneInUpperByte            'increment responseNum
'                                jmp         #:outerLoop
'
'
'{ Perform Write
'  We still need to verify that the count is consistent with the payload length. }
'PerformWrite
'                                { verify count - for a write this means that the payload length
'                                  equals the data section size (count * type size in bytes) plus
'                                  the header size (eight bytes) }
'                                add         bytesRequested, #8
'                                cmp         bytesRequested, payloadLength       wz
'                        if_nz   mov         errorCode, #InvalidArgument             '...payload length inconsistent with count
'                        if_nz   jmp         #SendErrorResponse
'
'                                { at this point the header has been parsed and verified, and the
'                                  write will be performed -- if implemented }
'
'                                { all write responses consist of three bytes -- the header bytes
'                                  have already been prepared }
'                                mov         payloadLength, #3
'
'                                { what happens next depends on the data type }
'                                cmp         dataType, #2                        wz
'                        if_z    jmp         #WriteLongs
'                                cmp         dataType, #1                        wz
'                        if_z    mov         errorCode, #UnsupportedCommand          '...writeWords unimplemented
'                        if_z    jmp         #SendErrorResponse
'
'                            { fall through to WriteBytes }
'
'WriteBytes
':outerLoop                      mov         wrBuff, Payload+2
'                                add         :outerLoop, #1
'                                mov         wrInnerCount, count             'count is guaranteed initially non-zero by program logic
'                                max         wrInnerCount, #4
'                                sub         count, wrInnerCount         wz
':innerLoop                      wrbyte      wrBuff, address
'                                shr         wrBuff, #8
'                                add         address, #1
'                                djnz        wrInnerCount, #:innerLoop
'                        if_nz   jmp         #:outerLoop
'                                movs        :outerLoop, #Payload+2          'reset for next time
'                                jmp         #SendFinalResponse
'
'WriteLongs
':loop                           wrlong      Payload+2, address
'                                add         :loop, kOneInDField
'                                add         address, #4
'                                djnz        count, #:loop
'                                movd        :loop, #Payload+2               'reset for next time
'                                jmp         #SendFinalResponse
'

{ Send Error Response
  Usage:            mov     errorCode, #<errorCode>
                    jmp     #SendErrorResponse
  Error responses are to be sent only if the payload appears to be a valid PeekPoke command
    with a valid initial four byte header. }
SendErrorResponse
                                or          Payload, kErrorBit
                                mov         payloadLength, #5
                                jmp         #SendFinalResponse


{ Constants }
k7050           long    $7050           '"pP"
'k10000          long    $10000          '65536 = hub size
kErrorBit       long    $8000_0000
'kResponseBit    long    $80_0000        'bit 7 of byte 2
'kOneInUpperByte long    $0100_0000
'kOneInDField    long    $200

availableGroups     long    cImplementedGroups & cAllowedGroups


{ ==========  Begin Temporaries  ========== }


{ Registers 486 to 495 are reserved for temporaries. }

fit 486     'If this fails then either user code or the payload buffer must be reduced.
org 486

initShiftLimit      'The initialization shifting code will ignore registers at and above this address.

{ Temporaries }
{ These are the temporary variables used by PropCR. User code may also use these temporaries. 
  See the section "Temporaries" in the User Guide for details. }

{ The following five temporaries -- registers 486 to 490 -- preserve their values during a Send* call. }

tmp0
address
_rxWait0        res

tmp1
count
_rxWait1        res

tmp2
dataType
_rxResetOffset  res

tmp3
bytesRequested
_rxOffset       res

tmp4
_initDeviceID
_adminTmp               '_adminTmp must not alias a _tx* temporary
_rxNextAddr     res

{ The following five "v" temporaries -- registers 491 to 495 -- are undefined after a Send* call. }

tmp5v
wrBuff
_rcvyPrevPhsb
_initTmp
_txF16L
_rxF16L         res

tmp6v
rdInnerCount
wrInnerCount
_rcvyCurrPhsb
_initHub
_txLong
_rxLong         res

tmp7v
_initRxPin
_txF16U
_rxLeftovers    res

tmp8v
_initTxPin
_txRemaining
_rxRemaining    res

tmp9v
_initDeviceAddress
_txCount
_rxCountdown    res


fit 496

org Payload+1
errorCode       res
