import csv
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from src.assembler import to_ir, assemble
from src.interpreter import run_program

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tools -> src -> edu-vm
TESTS_DIR = PROJECT_ROOT / "tests"

MEM_SIZE = 65536
REGS = 32


_BYTES_RE = re.compile(r"^\s*#\s*EXPECT\s+BYTES\s*:\s*(.+?)\s*$", re.IGNORECASE)
_MEM_RE = re.compile(r"^\s*#\s*EXPECT\s+MEM\[(\d+)\]\s*=\s*(-?\d+)\s*$", re.IGNORECASE)
_REG_RE = re.compile(r"^\s*#\s*EXPECT\s+REG\[(\d+)\]\s*=\s*(-?\d+)\s*$", re.IGNORECASE)


@dataclass
class Expectations:
    expected_bytes: Optional[bytes] = None
    expected_mem: List[Tuple[int, int]] = None
    expected_reg: List[Tuple[int, int]] = None

    def __post_init__(self):
        if self.expected_mem is None:
            self.expected_mem = []
        if self.expected_reg is None:
            self.expected_reg = []


def parse_expectations_and_rows(path: Path) -> Tuple[Expectations, List[List[str]]]:
    """
    Reads CSV file and returns:
      - expectations parsed from comment lines
      - CSV rows (non-comment, non-empty) for assembler
    """
    exp = Expectations()
    rows: List[List[str]] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            stripped = raw.strip()

            if not stripped:
                continue

            # Parse expectations from comments
            if stripped.startswith("#"):
                m = _BYTES_RE.match(raw)
                if m:
                    # Allow spaces; hex bytes can be "4D F6 13 00" or "4DF61300"
                    hex_part = m.group(1).replace(" ", "")
                    exp.expected_bytes = bytes.fromhex(hex_part)
                    continue

                m = _MEM_RE.match(raw)
                if m:
                    addr = int(m.group(1))
                    val = int(m.group(2))
                    exp.expected_mem.append((addr, val))
                    continue

                m = _REG_RE.match(raw)
                if m:
                    idx = int(m.group(1))
                    val = int(m.group(2))
                    exp.expected_reg.append((idx, val))
                    continue

                # Other comments ignored
                continue

            # Non-comment: parse as CSV row
            reader = csv.reader([raw])
            row = next(reader, [])
            row = [c.strip() for c in row if c is not None]
            if row:
                rows.append(row)

    return exp, rows


def assert_expected_bytes(binary: bytes, expected: bytes):
    if binary != expected:
        raise AssertionError(
            "Machine code mismatch.\n"
            f"Expected: {expected.hex(' ')}\n"
            f"Actual:   {binary.hex(' ')}"
        )


def assert_expected_state(state: dict, exp: Expectations):
    mem = state.get("mem", [])
    regs = state.get("regs", [])

    for addr, val in exp.expected_mem:
        if addr < 0 or addr >= len(mem):
            raise AssertionError(f"MEM[{addr}] out of range (mem size={len(mem)})")
        if mem[addr] != val:
            raise AssertionError(f"MEM[{addr}] mismatch: expected {val}, got {mem[addr]}")

    for idx, val in exp.expected_reg:
        if idx < 0 or idx >= len(regs):
            raise AssertionError(f"REG[{idx}] out of range (regs={len(regs)})")
        if regs[idx] != val:
            raise AssertionError(f"REG[{idx}] mismatch: expected {val}, got {regs[idx]}")


def run_test(csv_path: Path):
    print(f"\n=== {csv_path.name} ===")

    exp, rows = parse_expectations_and_rows(csv_path)
    ir = to_ir(rows)
    binary = assemble(ir)

    # If EXPECT BYTES present: compare against the whole binary.
    # For spec tests, make the file contain only ONE instruction.
    if exp.expected_bytes is not None:
        if len(binary) != 4:
            raise AssertionError(
                f"EXPECT BYTES present, but program size is {len(binary)} bytes. "
                "For encoding tests, keep exactly one instruction (4 bytes)."
            )
        assert_expected_bytes(binary, exp.expected_bytes)


        if not exp.expected_mem and not exp.expected_reg:
            print("OK (encoding)")
            return None


    # Run interpreter if we have runtime expectations or if we just want a smoke test.
    # (You can skip interpreter when only EXPECT BYTES is present, but running is harmless.)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(binary)
        bin_path = f.name

    state = run_program(
        bin_path,
        mem_size=MEM_SIZE,
        regs_count=REGS,
        dump_xml=None,
        dump_range=None,
    )

    # Check MEM/REG expectations
    if exp.expected_mem or exp.expected_reg:
        assert_expected_state(state, exp)

    print("OK")
    return state


def main():
    csv_tests = sorted(TESTS_DIR.glob("*.csv"))
    if not csv_tests:
        print("No CSV tests found")
        return

    passed = 0
    failed = 0

    for test in csv_tests:
        try:
            run_test(test)
            passed += 1
        except Exception as e:
            failed += 1
            print(f"FAILED: {test.name}")
            print(e)
            # If you want to continue running remaining tests, comment the next line:
            raise

    print(f"\nPassed: {passed}, Failed: {failed}")


if __name__ == "__main__":
    main()
