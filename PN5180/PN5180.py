import spidev
import RPi.GPIO as GPIO
from gpiozero import DigitalInputDevice
import time
import sys
from abc import ABC, abstractmethod

from .definitions import *

class PN5180(ABC):
	def __init__(self, bus: int = 0, device: int = 0, debug=False):
		self._spi = spidev.SpiDev()
		self._spi.open(bus, device)
		self._spi.max_speed_hz = 50000
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(25, GPIO.IN)  # GPIO 25 is the Busy pin (Header 22)
		self.__debug = debug

	def _log(self, *args):
		if self.__debug:
			print(args)

	@staticmethod
	def _log_format_hex(data: [bytes]):
		return ' '.join(f"0x{i:02x}" for i in data)

	def _wait_ready(self):
		#self._log("Check Card Ready")
		if GPIO.input(25):
			while GPIO.input(25):
				self._log("Card Not Ready - Waiting for Busy Low")
				time.sleep(.01)
		#self._log("Card Ready, continuing conversation.")

	def _send(self, frame: [bytes]):
		self._wait_ready()
		self._spi.writebytes(frame)
		self._log("Sent Frame: ", self._log_format_hex(frame))
		self._wait_ready()

	def _read(self, length):
		return self._spi.readbytes(length)

	def _send_string(self, string: str):
		msg_array = [ord(letter) for letter in string]
		self._send(msg_array)

	def _write_register(self, address, content):
		self._send([0x00, address] + list(content))

	def _card_has_responded(self):
		"""
		The function CardHasResponded reads the RX_STATUS register, which indicates if a card has responded or not.
		Bits 0-8 of the RX_STATUS register indicate how many bytes where received.
		If this value is higher than 0, a Card has responded.
		:return:
		"""
		self._send([PN5180_READ_REGISTER, RX_STATUS])  # READ_REGISTER RX_STATUS -> Response > 0 -> Card has responded
		result = self._read(4)  # Read 4 bytes
		self._send([PN5180_READ_REGISTER, IRQ_STATUS])  # READ_REGISTER IRQ_STATUS
		result_irq = self._read(4)  # Read 4 bytes
		self._log("RX_STATUS", self._log_format_hex(result))
		self._log("IRQ_STATUS", self._log_format_hex(result_irq))
		collision_bit = int.from_bytes(result, byteorder='little', signed=False) >> 18 & 1
		collision_position = int.from_bytes(result, byteorder='little', signed=False) >> 19 & 0x3f
		self._collision_flag = collision_bit
		self._collision_position = collision_position
		if result[0] > 0:
			self._bytes_in_card_buffer = result[0]
			return True
		return False

	@abstractmethod
	def _inventory(self):
		"""
		Return UID when detected
		:return:
		"""
		raise NotImplementedError("Method needs to be subclassed for each protocol.")

	@staticmethod
	def _format_uid(uid):
		"""
		Return a readable UID from a LSB byte array
		:param uid:
		:return:
		"""
		uid_readable = list(uid)  # Create a copy of the original UID array
		#uid_readable.reverse()
		uid_readable = "".join([format(byte, 'x').zfill(2) for byte in uid_readable])
		# print(f"UID: {uid_readable}")
		return uid_readable

	def inventory(self, raw=False):
		"""
		Send inventory command for initialized protocol, returns a list of cards detected.
		'raw' parameter can be set to False to return the unstructured UID response from the card.
		:param raw:
		:return:
		"""
		cards = self._inventory()
		# print(f"{len(cards)} card(s) detected: {' - '.join([self._format_uid(card) for card in cards])}")
		if raw:
			return cards
		else:
			return [self._format_uid(card) for card in cards]


class ISO15693(PN5180):
	def __init__(self, bus: int = 0, device: int = 0, debug=False):
		super().__init__(bus, device, debug)

	def _inventory(self):
		"""
		Return UID when detected
		:return:
		"""
		uids = []
		# https://www.nxp.com/docs/en/application-note/AN12650.pdf
		self._send([PN5180_LOAD_RF_CONFIG, 0x0D, 0x8D])  # Loads the ISO 15693 protocol into the RF registers
		self._send([PN5180_RF_ON, 0x00])  # Switches the RF field ON.
		self._send([PN5180_WRITE_REGISTER, IRQ_CLEAR, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
		self._send([PN5180_WRITE_REGISTER_AND_MASK, SYSTEM_CONFIG, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
		self._send([PN5180_WRITE_REGISTER_OR_MASK, SYSTEM_CONFIG, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
		self._send([PN5180_SEND_DATA, 0x00, 0x06, 0x01, 0x00])  # Sends an inventory command with 16 slots

		for slot_counter in range(0, 16):  # A loop that repeats 16 times since an inventory command consists of 16 time slots
			if self._card_has_responded():  # The function CardHasResponded reads the RX_STATUS register, which indicates if a card has responded or not.
				#GPIO.output(16, GPIO.LOW)
				self._send([PN5180_READ_DATA, 0x00])  # Command READ_DATA - Reads the reception Buffer
				uid_buffer = self._read(self._bytes_in_card_buffer)  # We shall read the buffer from SPI MISO -  Everything in the reception buffer shall be saved into the UIDbuffer array.
				# uid_buffer = self._read(255)  # We shall read the buffer from SPI MISO
				self._log("Buffer:", self._log_format_hex(uid_buffer))
				# uid = uid_buffer[0:10]
				uids.append(uid_buffer)
			self._send([0x02, 0x18, 0x3F, 0xFB, 0xFF, 0xFF])  # Send only EOF (End of Frame) without data at the next RF communication.
			self._send([PN5180_WRITE_REGISTER_AND_MASK, SYSTEM_CONFIG, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
			self._send([PN5180_WRITE_REGISTER_OR_MASK, SYSTEM_CONFIG, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
			self._send([PN5180_WRITE_REGISTER, IRQ_CLEAR, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
			self._send([PN5180_SEND_DATA, 0x00])  # Send EOF
		self._send([PN5180_RF_OFF, 0x00])  # Switch OFF RF field
		#GPIO.output(16, GPIO.HIGH)
		return uids
		

class ISO14443(PN5180):
	def __init__(self, bus: int = 0, device: int = 0, debug=False):
		super().__init__(bus, device, debug)

	def _anticollision(self, cascade_level=0x93, uid_cln=[], uid=[]):
		self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_TX_CONFIG, 0xFE, 0xFF, 0xFF, 0xFF])  #Switches the CRC extension off in Tx direction
		self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_RX_CONFIG, 0xFE, 0xFF, 0xFF, 0xFF])  #Switches the CRC extension off in Rx direction
		self._send([PN5180_WRITE_REGISTER_AND_MASK, SYSTEM_CONFIG, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
		self._send([PN5180_WRITE_REGISTER_OR_MASK, SYSTEM_CONFIG, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
		self._send([PN5180_WRITE_REGISTER, IRQ_CLEAR, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
		self._send([PN5180_SEND_DATA, 0x00, cascade_level, 0x20])
		time.sleep(.5)
		if self._card_has_responded():
			self._send([PN5180_READ_DATA, 0x00])  # Command READ_DATA - Reads the reception Buffer
			data = self._read(5)  # We shall read the buffer from SPI MISO
			self._log("Buffer: ", self._log_format_hex(data))
			if self._collision_flag:
				self._log(f"Collision Occurred at position: {self._collision_position}")
			else:
				# No collision occurred
				self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_TX_CONFIG, 0x01])  #Switches the CRC extension on in Tx direction
				self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_RX_CONFIG, 0x01])  #Switches the CRC extension on in Rx direction
				self._send([PN5180_WRITE_REGISTER_AND_MASK, SYSTEM_CONFIG, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
				self._send([PN5180_WRITE_REGISTER_OR_MASK, SYSTEM_CONFIG, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
				self._send([PN5180_WRITE_REGISTER, IRQ_CLEAR, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
				self._send([PN5180_SEND_DATA, 0x00, cascade_level, 0x70]+data)
				if self._card_has_responded():
					self._send([PN5180_READ_DATA, 0x00])  # Command READ_DATA - Reads the reception Buffer
					sak = self._read(3)  # We shall read the buffer from SPI MISO
					self._log("Buffer: ", self._log_format_hex(sak))
					if data[0] == 0x88:
						# Cascade bit set, need to dig deeper
						partial_uid = data[1:4]
						return data[1:4] + self._anticollision(cascade_level=cascade_level+2, uid_cln=uid_cln+partial_uid)
					else:
						return data[:-1]
		raise Exception


	def _inventory(self):
		"""
		Return UID when detected
		:return:
		"""
		uids = []
		# https://www.nxp.com/docs/en/application-note/AN12650.pdf
		# https://www.nxp.com/docs/en/application-note/AN10834.pdf
		self._send([PN5180_LOAD_RF_CONFIG, 0x00, 0x80])  # Loads the ISO 14443 - 106 protocol into the RF registers
		self._send([PN5180_RF_ON, 0x00])  # Switches the RF field ON.
		self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_TX_CONFIG, 0xFE, 0xFF, 0xFF, 0xFF])  #Switches the CRC extension off in Tx direction
		self._send([PN5180_WRITE_REGISTER_AND_MASK, CRC_RX_CONFIG, 0xFE, 0xFF, 0xFF, 0xFF])  #Switches the CRC extension off in Rx direction
		self._send([PN5180_WRITE_REGISTER, IRQ_CLEAR, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
		self._send([PN5180_WRITE_REGISTER_AND_MASK, SYSTEM_CONFIG, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
		self._send([PN5180_WRITE_REGISTER_OR_MASK, SYSTEM_CONFIG, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
		time.sleep(0.005) # Wait 5 ms before sending REQA
		self._send([PN5180_SEND_DATA, 0x07, 0x26])  # Sends REQA command to check if at least 1 card in field

		if self._card_has_responded():
			self._send([PN5180_READ_DATA, 0x00])  # Command READ_DATA - Reads the reception Buffer
			atqa = self._read(self._bytes_in_card_buffer)  # We shall read the buffer from SPI MISO -  Everything in the reception buffer shall be saved into the UIDbuffer array.
			# uid_buffer = self._read(255)  # We shall read the buffer from SPI MISO
			self._log("Buffer:", self._log_format_hex(atqa))
			try:
				uid = self._anticollision()
				uids.append(uid)
			except Exception as e:
				pass
			#self._send([0x09, 0x07, 0x93, 0x20])
			#uid_buffer = self._read(self._bytes_in_card_buffer)  # We shall read the buffer from SPI MISO -  Everything in the reception buffer shall be saved into the UIDbuffer array.
			#self._log(uid_buffer)

		self._send([0x17, 0x00])  # Switch OFF RF field
		#GPIO.output(16, GPIO.HIGH)
		return uids