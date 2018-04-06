
con
    _xinfreq = 5_000_000
    _clkmode = xtal1 + pll16x


obj

    peekpoke : "PeekPoke.spin"

pub main

    peekpoke.setParams(31, 30, 230400, 10)

    peekpoke.new(@blinky)

    dira[27] := 1
    outa[27] := 1

    cognew(@Blinky, 0)

    repeat
        waitcnt(0)



dat

            long    0[100]

Blinky
org 0
            mov         0, #1
            shl         0, #26
            or          dira, 0
            or          outa, 0
            mov         cnt, cnt
            add         cnt, #9
:loop       waitcnt     cnt, pause
            xor         outa, 0
            jmp         #:loop
pause       long    4_000_000

