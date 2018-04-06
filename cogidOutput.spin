{
A short pasm program that will make one of the pins 0-7 a
high output depending on the cogid. After that, it sleeps
forever.
}

pub ignored


dat
                cogid       pinNum
                mov         pinMask, #1
                shl         pinMask, pinNum
                or          outa, pinMask
                or          dira, pinMask
                waitcnt     0, #0
                jmp         #$-1

pinNum      res
pinMask     res

