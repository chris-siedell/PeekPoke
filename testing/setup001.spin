{
setup001.spin
30 April 2018
source: https://github.com/chris-siedell/PeekPoke
python: https://pypi.org/project/peekpoke/
homepage: http://siedell.com/projects/PeekPoke/

Used for PeekPoke testing.
}

con

    _xinfreq = 5_000_000
    _clkmode = xtal1 + pll16x


obj
    
    peekpoke : "PeekPoke.spin"


var

    long buffer[1000]
    word addrTable[22]
    byte results[8]


pub main

    addrTable[0]  := @setupName
    addrTable[1]  := @empty
    addrTable[2]  := @a
    addrTable[3]  := @hi
    addrTable[4]  := @cat
    addrTable[5]  := @plop
    addrTable[6]  := @tulip
    addrTable[7]  := @cheese
    addrTable[8]  := @library
    addrTable[9]  := @elephant
    addrTable[10] := @processor
    addrTable[11] := @gettysburg
    addrTable[12] := @circleA
    addrTable[13] := @uint8List
    addrTable[14] := @sint8List
    addrTable[15] := @uint16List
    addrTable[16] := @sint16List
    addrTable[17] := @uint32List
    addrTable[18] := @sint32List
    addrTable[19] := @wordList
    addrTable[20] := @longList
    addrTable[21] := @buffer

    results[0] := peekpoke.start(@addrTable)

    peekpoke.setAddress(2)
    peekpoke.setReadRange(@buffer, @buffer + 3999)
    peekpoke.setWriteRange(@buffer, @buffer + 2999)
    results[1] := peekpoke.start(@buffer)

    peekpoke.setAddress(3)
    peekpoke.setReadRange(@buffer, @buffer)
    peekpoke.setWriteRange(@buffer + 1, @buffer + 1)
    results[2] := peekpoke.start(@buffer)

    peekpoke.setAddress(4)
    peekpoke.setPort(200)
    peekpoke.setBaudrate(57600)
    peekpoke.disableBreakDetection
    results[3] := peekpoke.start(0)

    peekpoke.setAddress(5)
    peekpoke.setPort(112)
    peekpoke.setBaudrate(115200)
    peekpoke.disableWriteHub
    peekpoke.disableSetSerialTimings
    results[4] := peekpoke.start(2018) 'expect 2016 due to zeroed low bits
   
    peekpoke.setAddress(6)
    peekpoke.enableWriteHub
    peekpoke.enableSetSerialTimings
    peekpoke.enableBreakDetection 
    results[5] := peekpoke.start($ffff) 'expect $fffc

    peekpoke.setAddress(7)
    peekpoke.setReadRange(0, $8fff)
    results[6] := peekpoke.start(@buffer)

    peekpoke.setAddress(8)
    results[7] := peekpoke.start(0) 'should fail to launch, returning 0
    peekpoke.init(cogid, @results)


dat

setupName   byte    "setup001", 0
empty       byte    0
a           byte    "a", 0
hi          byte    "hi", 0
cat         byte    "cat", 0
plop        byte    "plop", 0
tulip       byte    "tulip", 0
cheese      byte    "cheese", 0
library     byte    "library", 0
elephant    byte    "elephant", 0
processor   byte    "processor", 0
gettysburg  byte    9, "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.", 10, 9, "Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure. We are met on a great battle-field of that war. We have come to dedicate a portion of that field, as a final resting place for those who here gave their lives that that nation might live. It is altogether fitting and proper that we should do this.", 10, 9, "But, in a larger sense, we can not dedicate -- we can not consecrate -- we can not hallow -- this ground. The brave men, living and dead, who struggled here, have consecrated it, far above our poor power to add or detract. The world will little note, nor long remember what we say here, but it can never forget what they did here. It is for us the living, rather, to be dedicated here to the unfinished work which they who fought here have thus far so nobly advanced. It is rather for us to be here dedicated to the great task remaining before us -- that from these honored dead we take increased devotion to that cause for which they gave the last full measure of devotion -- that we here highly resolve that these dead shall not have died in vain -- that this nation, under God, shall have a new birth of freedom -- and that government of the people, by the people, for the people, shall not perish from the earth.", 0
circleA     byte    $e2, $92, $b6, 0    'utf-8 for 'A' in a circle

'All integer lists have five numbers.
uint8List   byte    200, 255, 0, 128, 1
sint8List   byte    -120, 127, 0, -128, -1
uint16List  word    50000, 65535, 0, 32768, 1
sint16List  word    -20500, 32767, 0, -32768, -1
uint32List  long    3000000000, 4294967295, 0, 2147483648, 1
sint32List  long    -2000000000, 2147483647, 0, -2147483648, -1
wordList    word    $aabb, $ccdd, $eeff, $0011, $2233
longList    long    $a0b0_c0d0, $e0f0_0010, $2030_4050, $6070_8090, $0a0b_0c0d
 

