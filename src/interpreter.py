#!/usr/bin/env python3
# interpreter.py
# CLI interpreter for Variant #21
# Usage:
#   python interpreter.py program.bin memory_dump.xml 100-220
#
# Memory is word-addressable (32-bit words).
# Command memory and data memory are combined into a single memory array.
#
# Variant #21 opcodes/fields:
# LOAD_CONST: A=13, bits: A(0-4,5), B(5-11,7), C(12-22,11)
#   regs[B] = C
# READ_MEM:  A=26, bits: A(0-4,5), B(5-11,7), C(12-18,7), D(19-24,6)
#   regs[C] = mem[ regs[B] + D ]
# WRITE_MEM: A=15, bits: A(0-4,5), B(5-11,7), C(12-25,14)
#   mem[C] = regs[B]
# POW:       A=22, bits: A(0-4,5), B(5-11,7), C(12-18,7), D(19-24,6), E(25-31,7)
#   op1 = mem[ regs[E] + D ]
#   op2 = mem[ regs[B] ]
#   regs[C] = pow(op1, op2)

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from src.utils import mask

INSTR_SIZE = 4  # bytes per instruction / word


def _check_addr(addr: int, mem_size: int, what: str = "memory access"):
    if addr < 0 or addr >= mem_size:
        raise IndexError(f"{what}: address {addr} out of bounds (0..{mem_size-1})")


def run_binary_bytes(code_bytes: bytes, mem_size: int = 1 << 16, regs_count: int = 32):
    """
    Run program from raw bytes (without reading a file).
    Program is loaded into mem starting at address 0 as 32-bit words.
    """
    if len(code_bytes) % INSTR_SIZE != 0:
        raise ValueError("Binary length must be multiple of 4 bytes (word-aligned instructions)")

    program_words = [
        int.from_bytes(code_bytes[i:i + INSTR_SIZE], "little")
        for i in range(0, len(code_bytes), INSTR_SIZE)
    ]

    state = {
        "regs": [0] * regs_count,
        "mem": [0] * mem_size,
        "pc": 0,
        "program_len": len(program_words),
    }

    if state["program_len"] > mem_size:
        raise MemoryError(f"Program too large: {state['program_len']} words, mem_size={mem_size}")

    # load program into combined memory
    for i, w in enumerate(program_words):
        state["mem"][i] = w

    # execute
    while state["pc"] < state["program_len"]:
        instr = state["mem"][state["pc"]]
        state["pc"] += 1
        decode_and_execute_one(instr, state)

    return state


def decode_and_execute_one(cmd_int: int, state: dict):
    """
    cmd_int: 32-bit instruction word
    state keys:
      regs: list[int]
      mem:  list[int] (combined)
      pc:   int (word index)
      program_len: int (in words)
    """
    regs = state["regs"]
    mem = state["mem"]
    mem_size = len(mem)

    A = cmd_int & mask(5)  # A is 5 bits in variant 21 (0..4)

    if A == 13:  # LOAD_CONST
        B = (cmd_int >> 5) & mask(7)     # reg addr
        C = (cmd_int >> 12) & mask(11)   # const
        if B < 0 or B >= len(regs):
            raise IndexError(f"LOAD_CONST: register B={B} out of bounds")
        regs[B] = int(C)
        return

    if A == 26:  # READ_MEM
        B = (cmd_int >> 5) & mask(7)     # base reg addr
        C = (cmd_int >> 12) & mask(7)    # dest reg addr
        D = (cmd_int >> 19) & mask(6)    # offset
        if B < 0 or B >= len(regs):
            raise IndexError(f"READ_MEM: register B={B} out of bounds")
        if C < 0 or C >= len(regs):
            raise IndexError(f"READ_MEM: register C={C} out of bounds")
        addr = int(regs[B]) + int(D)
        _check_addr(addr, mem_size, "READ_MEM")
        regs[C] = int(mem[addr])
        return

    if A == 15:  # WRITE_MEM
        B = (cmd_int >> 5) & mask(7)     # src reg addr
        C = (cmd_int >> 12) & mask(14)   # mem addr
        if B < 0 or B >= len(regs):
            raise IndexError(f"WRITE_MEM: register B={B} out of bounds")
        addr = int(C)
        _check_addr(addr, mem_size, "WRITE_MEM")
        mem[addr] = int(regs[B])
        return

    if A == 22:  # POW
        B = (cmd_int >> 5) & mask(7)     # reg addr for op2 address
        C = (cmd_int >> 12) & mask(7)    # dest reg
        D = (cmd_int >> 19) & mask(6)    # offset
        E = (cmd_int >> 25) & mask(7)    # base reg for op1 address

        if B < 0 or B >= len(regs):
            raise IndexError(f"POW: register B={B} out of bounds")
        if C < 0 or C >= len(regs):
            raise IndexError(f"POW: register C={C} out of bounds")
        if E < 0 or E >= len(regs):
            raise IndexError(f"POW: register E={E} out of bounds")

        addr1 = int(regs[E]) + int(D)
        _check_addr(addr1, mem_size, "POW operand1")
        op1 = int(mem[addr1])

        addr2 = int(regs[B])
        _check_addr(addr2, mem_size, "POW operand2")
        op2 = int(mem[addr2])

        # Integer pow (store as int word)
        regs[C] = int(pow(op1, op2))
        return

    raise ValueError(f"Unknown opcode A={A}")


def run_program(bin_path: str, mem_size: int = 1 << 16, regs_count: int = 32,
                dump_xml: str | None = None, dump_range: tuple[int, int] | None = None):
    p = Path(bin_path)
    if not p.exists():
        raise FileNotFoundError(bin_path)

    code_bytes = p.read_bytes()
    if len(code_bytes) % INSTR_SIZE != 0:
        raise ValueError("Binary length must be multiple of 4 bytes (word-aligned instructions)")

    # Load & run via helper
    state = run_binary_bytes(code_bytes, mem_size=mem_size, regs_count=regs_count)

    # dump XML if requested
    if dump_xml is not None and dump_range is not None:
        start, end = dump_range
        if start < 0 or end < 0 or start > end:
            raise ValueError("Invalid dump range")
        if end >= mem_size:
            raise IndexError("Dump range out of bounds")

        root = ET.Element("memory")
        for addr in range(start, end + 1):
            cell = ET.SubElement(root, "cell")
            cell.set("address", str(addr))
            cell.set("value", str(state["mem"][addr]))

        tree = ET.ElementTree(root)
        Path(dump_xml).parent.mkdir(parents=True, exist_ok=True)
        tree.write(dump_xml, encoding="utf-8", xml_declaration=True)

    return state


def parse_range(s: str):
    # format "start-end"
    if "-" not in s:
        raise argparse.ArgumentTypeError("Range must be start-end")
    a, b = s.split("-", 1)
    return (int(a), int(b))


def main():
    parser = argparse.ArgumentParser(description="Interpreter for UVM Variant #21")
    parser.add_argument("binary", help="Path to binary program")
    parser.add_argument("dump_xml", help="Path to XML dump file")
    parser.add_argument("range", help="Memory dump range start-end (e.g. 100-220)")
    parser.add_argument("--mem-size", type=int, default=1 << 16, help="Total memory size (words)")
    parser.add_argument("--regs", type=int, default=32, help="Number of registers")
    args = parser.parse_args()

    dump_range = parse_range(args.range)
    run_program(
        args.binary,
        mem_size=args.mem_size,
        regs_count=args.regs,
        dump_xml=args.dump_xml,
        dump_range=dump_range,
    )
    print("Program executed. Dump written to", args.dump_xml)


if __name__ == "__main__":
    main()
