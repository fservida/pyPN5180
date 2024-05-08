# Straight from https://github.com/ATrappmann/PN5180-Library/tree/master

# PN5180 1-Byte Direct Commands
# see 11.4.3.3 Host Interface Command List
PN5180_WRITE_REGISTER           = 0x00
PN5180_WRITE_REGISTER_OR_MASK   = 0x01
PN5180_WRITE_REGISTER_AND_MASK  = 0x02
PN5180_READ_REGISTER            = 0x04
PN5180_WRITE_EEPROM             = 0x06
PN5180_READ_EEPROM              = 0x07
PN5180_SEND_DATA                = 0x09
PN5180_READ_DATA                = 0x0A
PN5180_SWITCH_MODE              = 0x0B
PN5180_LOAD_RF_CONFIG           = 0x11
PN5180_RF_ON                    = 0x16
PN5180_RF_OFF                   = 0x17

# PN5180 Registers
SYSTEM_CONFIG       = 0x00
IRQ_ENABLE          = 0x01
IRQ_STATUS          = 0x02
IRQ_CLEAR           = 0x03
TRANSCEIVE_CONTROL  = 0x04
TIMER1_RELOAD       = 0x0c
TIMER1_CONFIG       = 0x0f
RX_WAIT_CONFIG      = 0x11
CRC_RX_CONFIG       = 0x12
RX_STATUS           = 0x13
CRC_TX_CONFIG       = 0x19
RF_STATUS           = 0x1d
SYSTEM_STATUS       = 0x24
TEMP_CONTROL        = 0x25

# PN5180 EEPROM Addresses
DIE_IDENTIFIER      = 0x00
PRODUCT_VERSION     = 0x10
FIRMWARE_VERSION    = 0x12
EEPROM_VERSION      = 0x14
IRQ_PIN_CONFIG      = 0x1A
