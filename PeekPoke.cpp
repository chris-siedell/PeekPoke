
#include <math.h>

#include <iomanip>
#include <iostream>
#include <sstream>

#include "PeekPoke.hpp"

std::string strForPeekPokeError(uint8_t errorCode); 


class PeekPoke::PropCRMonitor : public propcr::StatusMonitor {

public:

    PropCRMonitor(PeekPoke& parent) : parent(parent) {}
    
    virtual void transactionWillBegin(propcr::PropCR& host, propcr::Transaction transaction, void* context) {} // exceptions cause the transaction to abort
   
    virtual void transactionDidEnd(propcr::PropCR& host, propcr::Transaction transaction, void* context,
                                   propcr::Error error, const std::string& errorDetails,
                                   const propcr::HostTransactionStats& stats) noexcept {
        if (error != propcr::Error::None) {
            parent.errorOccurred = true;
            parent.errorString = "Crow transaction failed. Error: " + propcr::strForError(error) + ", details: " + errorDetails + ".";
        }
        { 
            std::lock_guard<std::mutex> lock(parent.mutex);
            parent.isDone = true;
        }
        parent.waitCondition.notify_all();
    }

    // For responses to user commands.
    virtual void responseReceived(propcr::PropCR& host,
                                  const std::vector<uint8_t>& payload,
                                  bool isFinal,
                                  void* context,
                                  std::chrono::milliseconds& timeout,   // changes apply to future responses within this transaction
                                  const propcr::HostTransactionStats& stats) {

        if (parent.detailsByte & 0x04) {
            // write command
            if (!isFinal) {
                parent.errorOccurred = true;
                parent.errorString = "Unexpected intermediate response from write command.";
            } else if (payload.size() == 3 || payload.size() == 4) {
                if (payload[0] != 0x50 || payload[1] != 0x50) {
                    parent.errorOccurred = true;
                    std::stringstream ss;
                    ss << "Invalid response header -- initial bytes not 0x5050.";
                    parent.errorString = ss.str();
                } else if ((payload[2] & 0xb8) != 0x80) {
                    parent.errorOccurred = true;
                    parent.errorString = "Invalid response header -- reserved bits not correct.";
                } else if ((payload[2] & 0x07) != (parent.detailsByte & 0x07)) {
                    parent.errorOccurred = true;
                    parent.errorString = "Invalid response header -- incorrect command details.";
                } else if (payload[2] & 0x40) {
                    // possible error response
                    if (payload.size() != 4) {
                        parent.errorOccurred = true;
                        parent.errorString = "Invalid response header -- incorrect length for possible error response.";
                    } else {
                        parent.errorOccurred = true;
                        parent.errorString = "PeekPoke error: " + strForPeekPokeError(payload[3]);
                    }
                } else {
                    // possible non-error response
                    if (payload.size() != 3) {
                        parent.errorOccurred = true;
                        parent.errorString = "Invalid response header -- incorrect length for possible non-error response.";
                    } else {
                        parent.commandSuccess = true;
                    }
                }
            } else {
                parent.errorOccurred = true;
                std::stringstream ss;
                ss << "Unexpected payload size for write command (" << payload.size() << " bytes).";
                parent.errorString = ss.str();
            }
        } else {
            // read command
            
            if (context == NULL) {
                parent.errorOccurred = true;
                parent.errorString = "Unexpected NULL context in responseReceived handler.";
                return;
            }
            
            std::vector<uint32_t>* longs = static_cast<std::vector<uint32_t>*>(context);
           

            parent.responseCount += 1;

            if (parent.responseCount > parent.expectedResponseCount) {
                parent.errorOccurred = true;
                parent.errorString = "Too many responses received.";
                return;
            }

            if (isFinal && parent.responseCount < parent.expectedResponseCount) {
                parent.errorOccurred = true;
                parent.errorString = "Premature final response for read command.";
                return;
            }

            if (parent.responseCount == parent.expectedResponseCount && !isFinal) {
                parent.errorOccurred = true;
                parent.errorString = "Expected final response is not final.";
                return;
            }

            if (!isFinal && payload.size() != 516) {
                parent.errorOccurred = true;
                parent.errorString = "Unexpected intermediate read response size.";
                return;
            }

            if (payload.size() < 4) {
                parent.errorOccurred = true;
                parent.errorString = "Read response is too small.";
                return;
            }

            if (payload[0] != 0x50 || payload[1] != 0x50) {
                parent.errorOccurred = true;
                parent.errorString = "Invalid initial header bytes for read response.";
                return;
            }

            if ((payload[2] & 0xb8) != 0x80) {
                parent.errorOccurred =  true;
                parent.errorString = "Incorrect reserved bits for details byte of response header.";
                return;
            }           

            if ((payload[2] & 0x07) != (parent.detailsByte & 0x07)) {
                parent.errorOccurred =  true;
                parent.errorString = "Incorrect command details for read response.";
                return;
            }

            if (payload[2] & 0x40) {
                // possible error response
                
                if (payload.size() != 4) {
                    parent.errorOccurred =  true;
                    parent.errorString = "Incorrect payload size for read error response.";
                    return;
                }

                parent.errorOccurred = true;
                parent.errorString = "PeekPoke error: " + strForPeekPokeError(payload[3]);
                return;
            }

            if (payload[3] != (parent.responseCount - 1)) {
                parent.errorOccurred =  true;
                parent.errorString = "Incorrect response count number.";
                return;
            }

            if (isFinal && payload.size() != parent.numDataBytesInFinalResponse + 4) {
                parent.errorOccurred = true;
                parent.errorString = "Incorrect final read response size.";
                return;
            }
            
            if (parent.errorOccurred) {
               return;
            }

            // at this point we've established that if this is an intermediate response, the data section is 512 bytes long
            // and if it is a final response, the data section has the expected length 

            parent.readData.insert(parent.readData.begin(), payload.begin()+4, payload.end());
            
        }
    
    
    } // exceptions cause the transaction to abort

    // For the getDeviceInfo admin command.
    virtual void deviceInfoReceived(propcr::PropCR& host,
                                    propcr::DeviceInfo& deviceInfo,
                                    void* context,
                                    const propcr::HostTransactionStats& stats) noexcept {} // no exceptions allowed since the transaction is over

private:

    PeekPoke& parent;
};


PeekPoke::PeekPoke(const std::string& deviceName) : propCR(deviceName) {
    monitor = new PropCRMonitor(*this);
    propCR.setStatusMonitor(monitor);
    propCR.setBaudrate(115200);
}

PeekPoke::~PeekPoke() {
    propCR.setStatusMonitor(NULL);
    delete monitor;
}


void PeekPoke::writeBytes(uint16_t address, const std::vector<uint8_t>& bytes) {

    if (bytes.size() > 512) {
        throw std::runtime_error("Writes limited to 512 bytes.");
    }

    payload.resize(8);

    detailsByte = 0b00000100;

    payload[0] = 0x50;
    payload[1] = 0x50;
    payload[2] = detailsByte;
    payload[3] = 0x00;
    payload[4] = address;
    payload[5] = address >> 8;
    payload[6] = bytes.size() - 1;
    payload[7] = (bytes.size() - 1) >> 8;

    payload.insert(payload.end(), bytes.begin(), bytes.end());

    std::unique_lock<std::mutex> lock(mutex);
    
    isDone = false; // monitor sets to true when transaction is done
    errorOccurred = false; // monitor sets to true on errors
    commandSuccess = false; // monitor sets to true if command succeeds
   
    propCR.sendCommand(crowAddress, crowProtocol, payload);

    waitCondition.wait(lock, [this]{return isDone;});

    if (errorOccurred) {
        throw std::runtime_error(errorString);
    } else if (!commandSuccess) {
        throw std::runtime_error("The command failed for unknown reasons.");
    }
}

void PeekPoke::writeWords(uint16_t address, const std::vector<uint16_t>& words) {
    throw std::runtime_error("Not implemented.");
}

void PeekPoke::writeLongs(uint16_t address, const std::vector<uint32_t>& longs) {

    if (longs.size() > 128) {
        throw std::runtime_error("Writes limited to 128 longs.");
    }

    if (address % 4 != 0) {
        throw std::runtime_error("Long addresses must be multiples of four.");
    }
    
    payload.resize(8);

    detailsByte = 0b00000110;

    payload[0] = 0x50;
    payload[1] = 0x50;
    payload[2] = detailsByte;
    payload[3] = 0x00;
    payload[4] = address;
    payload[5] = address >> 8;
    payload[6] = longs.size() - 1;
    payload[7] = 0x00;

    for (uint32_t longValue : longs) {
        payload.push_back(longValue);
        payload.push_back(longValue >> 8);
        payload.push_back(longValue >> 16);
        payload.push_back(longValue >> 24);
    }

    std::unique_lock<std::mutex> lock(mutex);
    
    isDone = false; // monitor sets to true when transaction is done
    errorOccurred = false; // monitor sets to true on errors
    commandSuccess = false; // monitor sets to true if command succeeds
   
    propCR.sendCommand(crowAddress, crowProtocol, payload);

    waitCondition.wait(lock, [this]{return isDone;});

    if (errorOccurred) {
        throw std::runtime_error(errorString);
    } else if (!commandSuccess) {
        throw std::runtime_error("The command failed for unknown reasons.");
    }
}



void PeekPoke::readBytes(uint16_t address, uint16_t count, std::vector<uint8_t>& bytes) {
    throw std::runtime_error("Not implemented.");
/*
    if (count == 0) {
        throw std::runtime_error("Count must be non-zero.");
    }

    uint16_t longAddr = address & (~0b11);
    uint16_t lastLongAddr = (address + count) & (~0b11);
    uint16_t longCount = lastLongAddr - longAddr + 1;

    std::vector<uint32_t> longs;

    readLongs(longAddr, longCount, longs);

    bytes.clear();


    int numInitSyncBytes = 4 - (address - longAddr);
    if (numInitSyncBytes > count) numInitSyncBytes = count;



    for (int i = 0; i < numInitSyncBytes; ++i) {
        bytes.push_back = longs[0];
        longs[0] >> 8;
    }
*/
}

void PeekPoke::readWords(uint16_t address, uint16_t count, std::vector<uint16_t>& words) {
    throw std::runtime_error("Not implemented.");
}

void PeekPoke::readLongs(uint16_t address, uint16_t count, std::vector<uint32_t>& longs) {

    if (count > 16384) {
        throw std::runtime_error("Reads are limited to 16384 longs.");
    }

    if (address % 4 != 0) {
        throw std::runtime_error("Long addresses must be multiples of four.");
    }

    payload.resize(8);

    detailsByte = 0b00000010;

    payload[0] = 0x50;
    payload[1] = 0x50;
    payload[2] = detailsByte;
    payload[3] = 0x00;
    payload[4] = address;
    payload[5] = address >> 8;
    payload[6] = count - 1;
    payload[7] = (count - 1) >> 8;

    longs.clear();

    std::unique_lock<std::mutex> lock(mutex);
   
    readData.clear();

    isDone = false; // monitor sets to true when transaction is done
    errorOccurred = false; // monitor sets to true on errors
    commandSuccess = false; // monitor sets to true if command succeeds
  
    expectedResponseCount = ceil( count * 4.0 / 512.0);
    responseCount = 0;

    numDataBytesInFinalResponse = (count * 4) % 512;

    propCR.sendCommand(crowAddress, crowProtocol, payload, false, &longs);

    waitCondition.wait(lock, [this]{return isDone;});

    if (errorOccurred) {
        throw std::runtime_error(errorString);
    }

    int totalBytes = (expectedResponseCount - 1)*512 + numDataBytesInFinalResponse;

    if (totalBytes != readData.size()) {
        throw std::runtime_error("Incorrect number of bytes read.");
    }
    
    for (int i = 0; i < readData.size(); i += 4) { // should have already established that readData.size() % 4 == 0
        uint32_t value = readData[i] | readData[i+1] << 8 | readData[i+2] << 16 | readData[i+3] << 24;
        longs.push_back(value);
    }
}

std::string strForPeekPokeError(uint8_t errorCode) {
    switch (errorCode) {

    case 0:
        return "Unspecified.";
    case 1:
        return "Unsupported command.";
    case 2:
        return "Missing argument(s).";
    case 3:
        return "Invalid argument(s).";
    case 4:
        return "Range error.";
    case 5:
        return "Command prohibited.";
    default:
        std::stringstream ss;
        ss << std::setw(2) << std::uppercase << std::hex;
        ss << "Unknown error code (" << static_cast<int>(errorCode) << ").";
        return ss.str();
    }
}

