{
A short pasm program that will make one of the pins 0-31 a
high output depending on par. Specifically, bits 2-6 determine
which pin to use. After setting up the pin the program sleeps
forever.
}

pub ignored


dat
                mov         pinNum, par
                shr         pinNum, #2
                mov         pinMask, #1
                shl         pinMask, pinNum
                or          outa, pinMask
                or          dira, pinMask
                waitcnt     0, #0
                jmp         #$-1

pinNum      res
pinMask     res

