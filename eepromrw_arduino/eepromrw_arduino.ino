/**
* eepromrw - Arduino / ESP32 compatible Sketch
* 
* For more info, check the github wiki 'Arduino' page!
*
* by EnWaffel
*/

#include "Config.h"
#include "24AA512.h"

static constexpr const char* CHIPS_LIST[] = {
  "24AA512"
};
static constexpr uint8_t CHIPS_LIST_SIZE = 1;

void process_command();

void setup()
{
  Serial.begin(BAUD);
}

void loop()
{
  if (Serial.available() > 0)
  {
    process_command();
  }  
}

void ack()
{
  Serial.write("ack");
}

void nck()
{
  Serial.write("nck");
}

void process_command()
{
  char buf[4];
  buf[3] = 0;
  Serial.readBytes(buf, sizeof(buf) - 1);
 
  if (strcmp(buf, "rst") == 0)
  {
    // TODO: Add reset
  }
  else if (strcmp(buf, "wrt") == 0)
  {
    String chip = Serial.readStringUntil(';');
    
    if (chip == "24AA512")
    {
      ack();
      chip_24AA512_write();
    }
    else
    {
      nck();
    }
  }
  else if (strcmp(buf, "rd ") == 0)
  {
    String chip = Serial.readStringUntil(';');
    
    if (chip == "24AA512")
    {
      ack();
      chip_24AA512_read();
    }
    else
    {
      nck();
    }
  }
  else
  {
    nck(); // Not acknowledge; unknown command
  }
}
