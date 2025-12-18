import argparse
import csv
from pathlib import Path

from src.utils import pack_fields

INSTR_SIZE = 4

# =========================
# Variant #21 encoding
# =========================
# LOAD_CONST:
# A=13, bits: A 0-4 (5), B 5-11 (7), C 12-22 (11)
# Operand: C (const). Result: reg[B]
#
# READ_MEM:
# A=26, bits: A 0-4 (5), B 5-11 (7), C 12-18 (7), D 19-24 (6)
# Operand: mem[ regs[B] + D ]. Result: reg[C]
#
# WRITE_MEM:
# A=15, bits: A 0-4 (5), B 5-11 (7), C 12-25 (14)
# Operand: reg[B]. Result: mem[C]
#
# POW:
# A=22, bits: A 0-4 (5), B 5-11 (7), C 12-18 (7), D 19-24 (6), E 25-31 (7)
# op1 = mem[ regs[E] + D ]
# op2 = mem[ regs[B] ]
# result -> reg[C]


def encode_instr(ir: dict) -> bytes:
    cmd_name = ir["cmd"]

    if cmd_name == "LOAD_CONST":
        A = 13
        B = int(ir["B"])  # reg addr
        C = int(ir["C"])  # const
        val = pack_fields([
            (A, 0, 5),
            (B, 5, 7),
            (C, 12, 11),
        ])
        return val.to_bytes(INSTR_SIZE, "little")

    if cmd_name == "READ_MEM":
        A = 26
        B = int(ir["B"])  # base reg addr
        C = int(ir["C"])  # dest reg addr
        D = int(ir["D"])  # offset
        val = pack_fields([
            (A, 0, 5),
            (B, 5, 7),
            (C, 12, 7),
            (D, 19, 6),
        ])
        return val.to_bytes(INSTR_SIZE, "little")

    if cmd_name == "WRITE_MEM":
        A = 15
        B = int(ir["B"])  # src reg addr
        C = int(ir["C"])  # mem addr
        val = pack_fields([
            (A, 0, 5),
            (B, 5, 7),
            (C, 12, 14),
        ])
        return val.to_bytes(INSTR_SIZE, "little")

    if cmd_name == "POW":
        A = 22
        B = int(ir["B"])  # reg addr holding address for op2
        C = int(ir["C"])  # dest reg addr
        D = int(ir["D"])  # offset
        E = int(ir["E"])  # base reg addr for op1
        val = pack_fields([
            (A, 0, 5),
            (B, 5, 7),
            (C, 12, 7),
            (D, 19, 6),
            (E, 25, 7),
        ])
        return val.to_bytes(INSTR_SIZE, "little")

    raise ValueError(f"Unknown IR command: {cmd_name}")


def parse_csv_program(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    program_rows = []
    with open(p, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            # allow comments with leading '#'
            first = row[0].strip()
            if not first or first.startswith("#"):
                continue
            # trim all fields
            row = [c.strip() for c in row if c is not None]
            if len(row) == 0:
                continue
            program_rows.append(row)

    return program_rows


def to_ir(csv_rows):
    """
    Expected CSV (recommended simple form):
      LOAD_CONST,B,C
      READ_MEM,B,C,D
      WRITE_MEM,B,C
      POW,B,C,D,E

    Where:
      - B, C, D, E are integers (field meanings per spec above)
    """
    ir = []
    for idx, row in enumerate(csv_rows):
        cmd = row[0].upper()

        def need(n: int):
            if len(row) != n:
                raise ValueError(f"{cmd} expects {n-1} args, got {len(row)-1} at line {idx+1}: {row}")

        if cmd == "LOAD_CONST":
            need(3)
            B = int(row[1])
            C = int(row[2])
            ir.append({"cmd": "LOAD_CONST", "B": B, "C": C})

        elif cmd == "READ_MEM":
            need(4)
            B = int(row[1])
            C = int(row[2])
            D = int(row[3])
            ir.append({"cmd": "READ_MEM", "B": B, "C": C, "D": D})

        elif cmd == "WRITE_MEM":
            need(3)
            B = int(row[1])
            C = int(row[2])
            ir.append({"cmd": "WRITE_MEM", "B": B, "C": C})

        elif cmd == "POW":
            need(5)
            B = int(row[1])
            C = int(row[2])
            D = int(row[3])
            E = int(row[4])
            ir.append({"cmd": "POW", "B": B, "C": C, "D": D, "E": E})

        else:
            raise ValueError(f"Unknown command '{cmd}' at line {idx+1}: {row}")

    return ir


def assemble(ir_list):
    binary = bytearray()
    for instr in ir_list:
        binary.extend(encode_instr(instr))
    return binary


def fmt_bytes_hex(b: bytes):
    return ", ".join(f"0x{x:02X}" for x in b)


def main():
    parser = argparse.ArgumentParser(description="Assembler for UVM Variant #21 (CSV -> BIN)")
    parser.add_argument("input", help="Path to CSV input (program)")
    parser.add_argument("output", help="Path to binary output")
    parser.add_argument("--test", action="store_true", help="Test mode: print IR and bytes")
    args = parser.parse_args()

    rows = parse_csv_program(args.input)
    ir = to_ir(rows)

    if args.test:
        print("=== IR ===")
        for i, instr in enumerate(ir):
            print(f"{i:03}: {instr}")

    binary = assemble(ir)
    with open(args.output, "wb") as f:
        f.write(binary)

    print(f"Wrote binary '{args.output}' ({len(binary)} bytes).")

    if args.test:
        print("Bytes (hex):")
        print(fmt_bytes_hex(binary))


if __name__ == "__main__":
    main()
