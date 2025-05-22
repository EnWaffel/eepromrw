import argparse
import serial
import serial.tools.list_ports
import time
from typing import Optional
import os
import math
import struct
import zlib

ser: Optional[serial.Serial] = None
CHUNK_SIZE = 16
BAUD = 115200

def find_lowest_bar_divider(chunks):
    for i in range(64):
        if math.floor(chunks / (i + 1)) <= 30:
            return math.floor(i + 1)
    return 64

def wait_for_ack():
    if ser is None:
        return
    while True:
        if ser.in_waiting < 3: continue
        b: bytes = ser.read(3)
        return b == b"ack"
    return False

def serial_port_exists(port_name: str) -> bool:
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return port_name in ports

def init_serial(port) -> bool:
    if not serial_port_exists(port):
        print("ERROR: Serial port not found: " + port)
        return False
    global ser
    ser = serial.Serial(port, BAUD, timeout=3)
    time.sleep(1)
    if not ser.is_open:
        return False
    return True

def do_write_chunk(file, chunk):
    if ser is None: return False

    b: bytes = file.buffer.read(chunk) # Read chunk from file

    ser.write(b"chk") # Tell the controller to wait for a chunk to arrive
    if not wait_for_ack():
        print("\nERROR: Failed to send chunk: received nack (announcing chunk)")
        return False
    
    size = len(b)
    checksum = sum(b) % 256

    ser.write(struct.pack("<H", size)) # Tell the controller the size of the chunk (unsigned 16 bit aka unsigned short aka uint16_t)
    if not wait_for_ack():
        print("\nERROR: Failed to send chunk: received nack (writing chunk size)")
        return False
    
    ser.write(b) # Write the actual chunk

    if not wait_for_ack():
        print("\nERROR: Failed to send chunk: received nack (writing chunk)")
        return False
    
    ser.write(struct.pack("<I", checksum)) # Tell the controller the checksum of the chunk (32 bit)
    if not wait_for_ack():
        #print("\nWARNING: Failed to send chunk: wrong checksum; resending...")
        return do_write_chunk(file, chunk)

    return True

def do_write(port: str, chip: str, fileName: str) -> None:
    print(f"INFO: Writing {fileName} to an {chip} via {port}")

    file = None

    try:
        file = open(fileName, "r")
    except FileNotFoundError:
        print(f"ERROR: File not found: {fileName}")
        return
    except IOError as e:
        print(f"ERROR: Failed to open file ({fileName}): {e}")
        return

    print("INFO: Opening serial port...")
    if not init_serial(port):
        print("ERROR: Failed to open serial port: " + port)
        return
    if ser is None:
        return
    
    ser.write(b"rst") # Reset controller
    ser.write(b"wrt") # Set controller to writing mode
    ser.write(chip.encode("utf-8") + b';') # Tell the controller what chip to write to
    if not wait_for_ack():
        print("ERROR: Failed to comminucate with controller (nack received)")
        return

    print("INFO: Controller ready!")
    print("INFO: Starting to write...")

    fileSize = os.path.getsize(fileName)
    chunks = math.floor(fileSize / CHUNK_SIZE)
    remaining = fileSize - math.floor(chunks * CHUNK_SIZE)
    divider = find_lowest_bar_divider(chunks)
    barChunks = math.floor(chunks / divider)

    print(f"INFO: Chunks: {max(chunks, 1)} ({CHUNK_SIZE} bytes per chunk) Remaining: {remaining}")

    for i in range(chunks):
        bar = "[" + "#" * math.floor((i / divider)) + " " * (barChunks - math.floor((i / divider)) + 1) + "]"
        print(f"\rProgress: {math.floor((i / chunks) * 100)}% {bar} => Chunk #{i + 1}", end="", flush=True)

        if not do_write_chunk(file, CHUNK_SIZE):
            return

        time.sleep(0.05)

    bar = "[" + "#" * (barChunks + 1) + "]"
    print(f"\rProgress: {100}% {bar} => Chunk #{max(barChunks, 1)}", end="", flush=True)

    if not do_write_chunk(file, remaining):
        return
    time.sleep(0.05)

    print("\nDone!")

    file.close()

def do_read_chunk(file, chunk):
    if ser is None: return False

    ser.write(b"chk") # Tell the controller to send us a chunk
    if not wait_for_ack():
        print("\nERROR: Failed to read chunk: received nack (announcing chunk)")
        return False
    
    ser.write(struct.pack("<H", chunk)) # Tell the controller the size of the chunk (unsigned 16 bit aka unsigned short aka uint16_t)
    if not wait_for_ack():
        print("\nERROR: Failed to read chunk: received nack (sending chunk size)")
        return False
    
    _remoteChecksum: bytes = ser.read(4)
    remoteChecksum = struct.unpack('<I', _remoteChecksum)[0]

    b: bytes = ser.read(chunk)
    checksum = sum(b) % 256

    if checksum != remoteChecksum:
        ser.write(b"nck")
        return do_read_chunk(file, chunk)

    if len(b) < chunk:
        ser.write(b"nck")
        print("\nERROR: Failed to read chunk: missing data (reading chunk)")
        return False
    
    ser.write(b"ack")
    
    file.buffer.write(b)

    return True

def do_read(port: str, chip: str, fileName: str, amount: int):
    print(f"INFO: Reading (into {fileName}) from an {chip} via {port}")

    file = None

    try:
        file = open(fileName, "w")
    except FileNotFoundError:
        print(f"ERROR: File not found: {fileName}")
        return
    except IOError as e:
        print(f"ERROR: Failed to open file ({fileName}): {e}")
        return

    print("INFO: Opening serial port...")
    if not init_serial(port):
        print("ERROR: Failed to open serial port: " + port)
        return
    if ser is None:
        return
    
    ser.write(b"rst") # Reset controller
    ser.write(b"rd ") # Set controller to reading mode
    ser.write(chip.encode("utf-8") + b';') # Tell the controller what chip to read from
    if not wait_for_ack():
        print("ERROR: Failed to comminucate with controller (nack received)")
        return

    print("INFO: Controller ready!")
    print("INFO: Starting to read...")

    fileSize = amount
    chunks = math.floor(fileSize / CHUNK_SIZE)
    remaining = fileSize - math.floor(chunks * CHUNK_SIZE)
    divider = find_lowest_bar_divider(chunks)
    barChunks = math.floor(chunks / divider)

    print(f"INFO: Chunks: {max(chunks, 1)} ({CHUNK_SIZE} bytes per chunk) Remaining: {remaining}")

    for i in range(chunks):
        bar = "[" + "#" * math.floor((i / divider)) + " " * (barChunks - math.floor((i / divider)) + 1) + "]"
        print(f"\rProgress: {math.floor((i / chunks) * 100)}% {bar} => Chunk #{i + 1}", end="", flush=True)

        if not do_read_chunk(file, CHUNK_SIZE):
            return

        time.sleep(0.05)

    bar = "[" + "#" * (barChunks + 1) + "]"
    print(f"\rProgress: {100}% {bar} => Chunk #{max(barChunks, 1)}", end="", flush=True)

    if not do_read_chunk(file, remaining):
        return
    time.sleep(0.05)

    print("\nDone!")

    file.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A simple EEPROM writing and reading tool.")
    parser.add_argument("-c", help="Chip", nargs='?', default=None)
    parser.add_argument("-p", help="COM Port of the controller", nargs='?', default=None)
    parser.add_argument("-l", help="List all supported chips", action='store_true')
    parser.add_argument("--list", help="List all supported chips", action='store_true')
    parser.add_argument("-w", help="Write a file to an EEPROM", action='store_true')
    parser.add_argument("-r", help="Read a file from an EEPROM", action='store_true')
    parser.add_argument("-v", help="Verify the contents of an EEPROM", action='store_true')
    parser.add_argument("-f", help="An input or output file", nargs='?', default=None)
    parser.add_argument("-s", help="An amount", nargs='?', default=None, type=int)
    args = parser.parse_args()

    print("\neepromrw - A simple EEPROM writing and reading tool\n(v0.0.1)\nby EnWaffel\n")

    if not any(vars(args).values()):
        parser.print_help()
        return

    if args.list or args.l:
        print("Supported Chips:")
        print("- 24AA512")
        return
    
    if args.w:
        if not args.p:
            print("FATAL: No COM port specified")
            return
        if not args.f:
            print("FATAL: No input file")
            return
        if not args.c:
            print("FATAL: No chip specified")
            return
        do_write(args.p, args.c, args.f)

    if args.r:
        if not args.p:
            print("FATAL: No COM port specified")
            return
        if not args.f:
            print("FATAL: No input file")
            return
        if not args.c:
            print("FATAL: No chip specified")
            return
        if not args.s:
            print("FATAL: No read amount")
            return
        do_read(args.p, args.c, args.f, args.s)
    
    if ser is not None:
        ser.close()

    print("\nThanks for using eepromrw! Goodbye!")
    
main()