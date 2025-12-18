import sys
import traceback
import csv
import io

from PySide6.QtCore import Slot, Signal, QObject, QThread
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QSpinBox,
    QFileDialog, QMessageBox, QLineEdit
)

from src.assembler import to_ir, assemble
from src.gui_backend import run_binary_bytes


class WorkerSignals(QObject):
    finished = Signal(dict)   # payload: {'state': state, 'log': str, 'binary_len': int, 'dump_range': (start,end)}
    error = Signal(str)       # payload: traceback text


class AssembleRunWorker(QThread):
    """
    Worker thread: performs CSV->IR->assemble->run, emits signals with results.
    """
    def __init__(self, csv_text: str, mem_size: int, regs_count: int, dump_range_text: str):
        super().__init__()
        self.csv_text = csv_text
        self.mem_size = mem_size
        self.regs_count = regs_count
        self.dump_range_text = dump_range_text
        self.signals = WorkerSignals()

    def parse_range(self, s: str):
        if "-" not in s:
            raise ValueError("Range must be start-end")
        a, b = s.split("-", 1)
        return int(a.strip()), int(b.strip())

    def parse_csv_rows(self, text: str):
        reader = csv.reader(io.StringIO(text))
        rows = []
        for row in reader:
            if not row:
                continue
            first = (row[0] or "").strip()
            if not first or first.startswith("#"):
                continue
            rows.append([c.strip() for c in row])
        return rows

    def run(self):
        # This is executed in background thread: do not touch GUI here.
        try:
            log_lines = []

            def log(s):
                log_lines.append(str(s))

            rows = self.parse_csv_rows(self.csv_text)
            log("Converting CSV -> IR...")
            ir = to_ir(rows)
            log("IR:\n" + "\n".join(f"{i:03}: {instr}" for i, instr in enumerate(ir)))

            log("Assembling to bytes...")
            binary = assemble(ir)
            log(f"Assembled {len(binary)} bytes")

            log(f"Running interpreter (mem={self.mem_size}, regs={self.regs_count})...")
            state = run_binary_bytes(bytes(binary), mem_size=self.mem_size, regs_count=self.regs_count)

            # Validate dump range now (still safe here)
            start, end = self.parse_range(self.dump_range_text)
            if start < 0 or end >= self.mem_size or start > end:
                raise ValueError("Dump range out of bounds or invalid")

            payload = {
                "state": state,
                "log": "\n".join(log_lines),
                "binary_len": len(binary),
                "dump_range": (start, end)
            }
            self.signals.finished.emit(payload)
        except Exception:
            tb = traceback.format_exc()
            self.signals.error.emit(tb)


class UVMGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UVM (Variant 21)")
        self.resize(1000, 700)

        main_layout = QVBoxLayout(self)

        # Top: editor + controls
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(
            """# Команда,аргументы...
# LOAD_CONST,B,C
# WRITE_MEM,B,C
# READ_MEM,B,C,D
# POW,B,C,D,E
#
# Пример:
LOAD_CONST,0,123
WRITE_MEM,0,100
READ_MEM,0,1,0
"""
        )
        main_layout.addWidget(QLabel("Program (CSV assembler):"))
        main_layout.addWidget(self.editor, stretch=3)

        controls_row = QHBoxLayout()

        self.assemble_run_btn = QPushButton("Assemble & Run")
        controls_row.addWidget(self.assemble_run_btn)
        self.assemble_run_btn.clicked.connect(self.on_assemble_run)

        self.step_btn = QPushButton("Step (not implemented)")
        self.step_btn.setEnabled(False)
        controls_row.addWidget(self.step_btn)

        controls_row.addWidget(QLabel("Mem words:"))
        self.mem_size_spin = QSpinBox()
        self.mem_size_spin.setRange(1, 1 << 20)
        self.mem_size_spin.setValue(1 << 16)
        controls_row.addWidget(self.mem_size_spin)

        controls_row.addWidget(QLabel("Regs:"))
        self.regs_spin = QSpinBox()
        self.regs_spin.setRange(1, 1024)
        self.regs_spin.setValue(32)
        controls_row.addWidget(self.regs_spin)

        controls_row.addWidget(QLabel("Dump range (start-end):"))
        self.dump_range_edit = QLineEdit("100-220")
        controls_row.addWidget(self.dump_range_edit)

        self.load_btn = QPushButton("Load .csv")
        self.load_btn.clicked.connect(self.load_csv)
        controls_row.addWidget(self.load_btn)

        self.save_btn = QPushButton("Save .csv")
        self.save_btn.clicked.connect(self.save_csv)
        controls_row.addWidget(self.save_btn)

        main_layout.addLayout(controls_row)

        # Middle: Memory table
        main_layout.addWidget(QLabel("Memory dump:"))
        self.mem_table = QTableWidget()
        self.mem_table.setColumnCount(2)
        self.mem_table.setHorizontalHeaderLabels(["Addr", "Value"])
        main_layout.addWidget(self.mem_table, stretch=2)

        # Bottom: log
        main_layout.addWidget(QLabel("Log / IR / Hex:"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        main_layout.addWidget(self.log, stretch=1)

        self._current_worker = None

    def append_log(self, text: str):
        self.log.appendPlainText(text)

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV program", "", "CSV Files (*.csv);;All Files (*)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            self.editor.setPlainText(f.read())

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV program", "program.csv", "CSV Files (*.csv);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(self.editor.toPlainText())

    @Slot()
    def on_assemble_run(self):
        self.assemble_run_btn.setEnabled(False)
        self.append_log("Starting assemble & run...")

        csv_text = self.editor.toPlainText()
        mem_size = int(self.mem_size_spin.value())
        regs_count = int(self.regs_spin.value())
        dump_range_text = self.dump_range_edit.text().strip()

        worker = AssembleRunWorker(csv_text, mem_size, regs_count, dump_range_text)
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)
        self._current_worker = worker
        worker.start()

    @Slot(dict)
    def _on_worker_finished(self, payload: dict):
        state = payload["state"]
        log_text = payload["log"]
        binary_len = payload["binary_len"]
        start, end = payload["dump_range"]

        self.append_log(log_text)
        self.append_log(f"Assembled {binary_len} bytes")
        self.append_log("Program executed. Updating memory table...")

        count = end - start + 1
        self.mem_table.setRowCount(count)

        mem = state.get("mem", [])
        for i, addr in enumerate(range(start, end + 1)):
            self.mem_table.setItem(i, 0, QTableWidgetItem(str(addr)))
            try:
                val = mem[addr]
            except Exception:
                val = "<out of range>"
            self.mem_table.setItem(i, 1, QTableWidgetItem(str(val)))

        self.append_log("Memory dump updated")
        QMessageBox.information(self, "Success", "Program executed and memory dump updated.")
        self.assemble_run_btn.setEnabled(True)
        self._current_worker = None

    @Slot(str)
    def _on_worker_error(self, tb_text: str):
        self.append_log("Error during assemble/run:\n" + tb_text)
        QMessageBox.critical(self, "Error", "An error occurred. See log for details.")
        self.assemble_run_btn.setEnabled(True)
        self._current_worker = None


def start_program():
    app = QApplication(sys.argv)
    win = UVMGUI()
    win.show()
    sys.exit(app.exec())
