import spidev
import RPi.GPIO as GPIO
import sys
import binascii

class PN5180():
	def __init__(self, bus:int = 0, device:int = 0, debug=False):
		self._spi = spidev.SpiDev()
		self._spi.open(bus, device)
		self._spi.max_speed_hz = 50000
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(25, GPIO.IN)  # GPIO 25 is the Busy pin (Header 22)
		self.__debug = debug
		self.__log("this", 1, "s", "a test")

	def __log(self, *args):
		if self.__debug:
			print(args)

	def _wait_ready(self):
		self.__log("Check Card Ready")
		if GPIO.input(25):
			self.__log("Card Not Ready - Waiting for Busy Low")
			GPIO.wait_for_edge(25, GPIO.FALLING, timeout=10)
		self.__log("Card Ready, continuing conversation.")

	def _send(self, bytes: list):
		self._spi.writebytes(bytes)
		self.__log("Sent Frame: ", bytes)
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
		self._send([0x04, 0x13])  # READ_REGISTER RX_STATUS -> Response > 0 -> Card has responded
		result = self._read(4)  # Read 4 bytes
		print("Received", result)
		if result[0] > 0:
			self._bytes_in_card_buffer = result[0]
			return True
		return False

	def test_card(self):
		# https://www.nxp.com/docs/en/application-note/AN12650.pdf
		self._send([0x11, 0x0D, 0x8D])  # Loads the ISO 15693 protocol into the RF registers
		self._send([0x16, 0x00])  # Switches the RF field ON.
		self._send([0x00, 0x03, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
		self._send([0x02, 0x00, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
		self._send([0x01, 0x00, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
		self._send([0x09, 0x00, 0x06, 0x01, 0x00])  # Sends an inventory command with 16 slots

		for slot_counter in range(0, 16):  # A loop that repeats 16 times since an inventory command consists of 16 time slots
			if self._card_has_responded():  # The function CardHasResponded reads the RX_STATUS register, which indicates if a card has responded or not.
				self._send([0x0A, 0x00])  # Command READ_DATA - Reads the reception Buffer
				#uid_buffer = self._read(self._bytes_in_card_buffer)  # We shall read the buffer from SPI MISO -  Everything in the reception buffer shall be saved into the UIDbuffer array.
				uid_buffer = self._read(255)  # We shall read the buffer from SPI MISO
				self.__log(uid_buffer)
				uid = uid_buffer[0:9]
				uid.reverse()
				uid_readable = "".join([format(byte, 'x').zfill(2) for byte in uid])
				print(f"UID: {uid_readable}")
			self._send([0x02, 0x18, 0x3F, 0xFB, 0xFF, 0xFF])  # Send only EOF (End of Frame) without data at the next RF communication.
			self._send([0x02, 0x00, 0xF8, 0xFF, 0xFF, 0xFF])  # Sets the PN5180 into IDLE state
			self._send([0x01, 0x00, 0x03, 0x00, 0x00, 0x00])  # Activates TRANSCEIVE routine
			self._send([0x00, 0x03, 0xFF, 0xFF, 0x0F, 0x00])  # Clears the interrupt register IRQ_STATUS
			self._send([0x09, 0x00])  # Send EOF
		self._send([0x17, 0x00])  # Switch OFF RF field


check_debug = sys.argv[1] if len(sys.argv) == 2 else ''
debug = True if check_debug == '-v' else False
reader = PN5180(debug=debug)
reader.test_card()
