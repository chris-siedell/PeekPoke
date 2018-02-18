
#include <vector>
#include <thread>
#include <condition_variable>
#include <mutex>

#include "PropCR.hpp"


#ifndef PeekPoke_hpp
#define PeekPoke_hpp

/*
 * This is a simple, initial version.
 *
 * The read and write functions are blocking.
 *
 * This version is not thread safe.
 *
 * This version assumes the Propeller implementation supports
 * only the writeBytes, writeLongs, and readLongs commands (which is true of
 * PeekPoke-CC.spin). The public functions of the PC implementation (this
 * file) are implemented by composing those commands.
 */

class PeekPoke {


public:

    PeekPoke(const std::string& deviceName); 
    ~PeekPoke();

    // These may throw std::invalid_argument or std::runtime_error.
    
    void writeBytes(uint16_t address, const std::vector<uint8_t>& bytes);
    void writeWords(uint16_t address, const std::vector<uint16_t>& words); // not implemented
    void writeLongs(uint16_t address, const std::vector<uint32_t>& longs);

    // The read* functions clear and fill the referenced vector.
    // These may throw std::invalid_argument or std::runtime_error.
    
    void readBytes(uint16_t address, uint32_t count, std::vector<uint8_t>& bytes); // implemented with readLongs
    void readWords(uint16_t address, uint16_t count, std::vector<uint16_t>& words); // not implemented
    void readLongs(uint16_t address, uint16_t count, std::vector<uint32_t>& longs);

    std::string getDeviceName();

    uint32_t getBaudrate();
    void setBaudrate(uint32_t baudrate);

    uint8_t getCrowAddress();
    void setCrowAddress(uint8_t address);


private:

    std::vector<uint8_t> payload;

    uint8_t crowAddress = 1;
    uint16_t crowProtocol = 0xAFAF;

    uint8_t detailsByte;

    std::mutex mutex;
    std::condition_variable waitCondition;
    bool isDone;
    std::string errorString;
    bool errorOccurred;
    bool commandIsRead;
    bool commandIsWrite;
   
    bool commandSuccess;

    // these apply to read commands
    ssize_t expectedResponseCount;
    ssize_t responseCount;
    ssize_t numDataBytesInFinalResponse;

    std::vector<uint8_t> readData;

    propcr::PropCR propCR;

    class PropCRMonitor;

    friend class PropCRMonitor;

    PropCRMonitor* monitor;
};

#endif

