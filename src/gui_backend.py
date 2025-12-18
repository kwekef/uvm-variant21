from pathlib import Path
import tempfile

from src.interpreter import run_program


def run_binary_bytes(binary_bytes: bytes, mem_size: int = 1 << 16, regs_count: int = 32):
    """
    Helper for GUI: run already-assembled binary bytes and return interpreter state.
    Variant #21: combined memory -> use mem_size (not data_mem_size).
    We don't generate XML dump here; GUI reads state["mem"] directly.
    """
    with tempfile.NamedTemporaryFile(prefix="uvm_", suffix=".bin", delete=False) as tf:
        tf.write(binary_bytes)
        tmp_path = Path(tf.name)

    try:
        state = run_program(
            str(tmp_path),
            mem_size=mem_size,
            regs_count=regs_count,
            dump_xml=None,
            dump_range=None,
        )
        return state
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
