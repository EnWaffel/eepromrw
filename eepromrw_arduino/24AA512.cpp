#include "Config.h"

#include <Arduino.h>
#include <Wire.h>
#include <Arduino_CRC32.h>

extern void ack();
extern void nck();

static uint16_t addressOffset;
Arduino_CRC32 crc32;

static byte simpleChecksum(const byte* data, size_t length) {
  unsigned int sum = 0;
  for (size_t i = 0; i < length; i++) {
    sum += data[i];
  }
  return (byte)(sum & 0xFF);
}

static void write_chunk()
{
  uint16_t chunkSize;
  uint8_t chunk[CHUNK_SIZE];

  Serial.readBytes((uint8_t*)&chunkSize, sizeof(chunkSize));

  if (chunkSize > CHUNK_SIZE)
  {
    nck();
    return;
  }

  ack();

  if (Serial.readBytes(chunk, chunkSize) != chunkSize)
  {
    nck();
    return;
  }

  uint32_t checksum = simpleChecksum(chunk, chunkSize);

  ack();

  uint32_t remoteChecksum;
  Serial.readBytes((uint8_t*)&remoteChecksum, sizeof(remoteChecksum));
  
  if (remoteChecksum != checksum)
  {
    nck();
    return;
  }

  ack();

  delay(5);

  Wire.beginTransmission(0x50);
  Wire.write(addressOffset >> 8);
  Wire.write(addressOffset & 0xFF);
  Wire.write(chunk, chunkSize);
  int result = Wire.endTransmission();
  if (result != 0)
  {
    nck();
    return;
  }

  addressOffset += chunkSize;

  ack();
} 

void chip_24AA512_write()
{
  addressOffset = 0;
  Wire.begin();

  while (true)
  {
    if (Serial.available() <= 0) continue;
    char cmdBuf[4];
    cmdBuf[3] = 0;
    Serial.readBytes(cmdBuf, sizeof(cmdBuf) - 1);
    
    if (strcmp(cmdBuf, "rst") == 0)
    {
      break;
    }
    else if (strcmp(cmdBuf, "chk") == 0)
    {
      ack();
      write_chunk();
    }
    else
    {
      nck();
    }
  }
}

static void read_chunk()
{
  uint16_t chunkSize;
  uint8_t chunk[CHUNK_SIZE];

  Serial.readBytes((uint8_t*)&chunkSize, sizeof(chunkSize));

  if (chunkSize > CHUNK_SIZE)
  {
    nck();
    return;
  }

  ack();

  Wire.beginTransmission(0x50);
  Wire.write(addressOffset >> 8);
  Wire.write(addressOffset & 0xFF);
  int result = Wire.endTransmission();
  if (result != 0)
  {
    nck();
    return;
  }

  delay(5);

  int received = Wire.requestFrom(0x50, chunkSize);

  uint16_t i = 0;
  while (Wire.available() > 0 && i < chunkSize)
  {
    chunk[i] = Wire.read();
    i++;
  }

  uint32_t checksum = simpleChecksum(chunk, chunkSize);
  Serial.write((uint8_t*)&checksum, sizeof(checksum));

  Serial.write(chunk, chunkSize);

  char buf[4];
  buf[3] = 0;
  Serial.readBytes(buf, sizeof(buf) - 1);

  if (strcmp(buf, "ack") != 0)
  {
    return;
  }

  addressOffset += chunkSize;
} 

void chip_24AA512_read()
{
  addressOffset = 0;
  Wire.begin();

  while (true)
  {
    if (Serial.available() <= 0) continue;
    char cmdBuf[4];
    cmdBuf[3] = 0;
    Serial.readBytes(cmdBuf, sizeof(cmdBuf) - 1);
    
    if (strcmp(cmdBuf, "rst") == 0)
    {
      break;
    }
    else if (strcmp(cmdBuf, "chk") == 0)
    {
      ack();
      read_chunk();
    }
    else
    {
      nck();
    }
  }
}