



pub ignored


dat

org 1

    or      dira, #1
    xor     outa, #1
    mov     payloadSize, #4
    jmp     SendResponseAddr


org 479

BreakHandlerAddr                res     '479    
SendResponseAddr                res     '480
SendErrorResponseAddr           res     '481 - set errorCode first
SendResponseAndReturnAddr_ret   res     '482 - so use "jmpret 482, 483" to send a response and return
SendResponseAndReturnAddr       res     '483
ReceiveCommandAddr              res     '484


payloadSize res    
