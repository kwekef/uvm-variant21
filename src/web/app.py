import io
import csv
import traceback
import tempfile
from flask import Flask, render_template, request, jsonify, send_file

from src.assembler import to_ir, assemble
from src.interpreter import run_program, parse_range

app = Flask(__name__)


@app.route('/')
def index():
    """Главная страница с редактором"""
    return render_template('index.html')


# ============================
# Assemble + Run (CSV -> BIN)
# ============================
@app.route('/api/assemble_run', methods=['POST'])
def api_assemble_run():
    try:
        data = request.json

        csv_text = data.get('csv', '')
        mem_size = int(data.get('mem_size', 65536))
        regs_count = int(data.get('regs_count', 32))
        dump_range_text = data.get('dump_range', '100-220')

        # --- CSV -> rows ---
        reader = csv.reader(io.StringIO(csv_text))
        csv_rows = [row for row in reader if row and not row[0].strip().startswith('#')]

        # --- CSV -> IR ---
        ir = to_ir(csv_rows)

        # --- IR -> binary ---
        binary = assemble(ir)

        # --- temp files ---
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(binary)
            temp_bin_path = f.name

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.xml') as f:
            temp_xml_path = f.name

        dump_range = parse_range(dump_range_text)

        try:
            # --- run interpreter ---
            state = run_program(
                temp_bin_path,
                mem_size=mem_size,
                regs_count=regs_count,
                dump_xml=temp_xml_path,
                dump_range=dump_range
            )

            # --- read XML dump ---
            import xml.etree.ElementTree as ET

            tree = ET.parse(temp_xml_path)
            root = tree.getroot()

            mem_dump = []
            for cell in root.findall("cell"):
                mem_dump.append({
                    "address": int(cell.get("address")),
                    "value": int(cell.get("value"))
                })

            return jsonify({
                "success": True,
                "ir": ir,
                "binary_size": len(binary),
                "binary_hex": binary.hex(),
                "mem_dump": mem_dump,
                "registers": state["regs"],
                "log": f"Assembled {len(binary)} bytes, executed successfully."
            })

        finally:
            try:
                import os
                os.unlink(temp_bin_path)
                os.unlink(temp_xml_path)
            except Exception:
                pass

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        })


# ============================
# Download binary
# ============================
@app.route('/api/download_binary', methods=['POST'])
def api_download_binary():
    try:
        data = request.json
        csv_text = data.get('csv', '')

        reader = csv.reader(io.StringIO(csv_text))
        csv_rows = [row for row in reader if row and not row[0].strip().startswith('#')]

        ir = to_ir(csv_rows)
        binary = assemble(ir)

        return send_file(
            io.BytesIO(binary),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='program.bin'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================
# Save CSV program
# ============================
@app.route('/api/save_csv', methods=['POST'])
def api_save_csv():
    try:
        data = request.json
        csv_text = data.get('csv', '')
        filename = data.get('filename', 'program.csv')

        if not filename.endswith('.csv'):
            filename += '.csv'

        return send_file(
            io.BytesIO(csv_text.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================
# Examples (CSV)
# ============================
@app.route('/api/example/<example_name>')
def api_example(example_name):
    examples = {
        "load_store": """# write 123 -> mem[100], read back to R1
LOAD_CONST,0,123
WRITE_MEM,0,100

LOAD_CONST,2,100
READ_MEM,2,1,0
""",

        "pow_simple": """# pow(2,3)=8 -> mem[800]
# MEM[600] = 2
LOAD_CONST,0,2
WRITE_MEM,0,600

# MEM[700] = 3
LOAD_CONST,0,3
WRITE_MEM,0,700

# R10 = 600  (E)
LOAD_CONST,10,600
# R11 = 700  (B holds address of exponent)
LOAD_CONST,11,700

# R12 = pow(MEM[R10+0], MEM[R11]) = pow(2,3) = 8
POW,11,12,0,10
WRITE_MEM,12,800
""",

        "copy_array": """# init source 300..302 then copy to 400..402
LOAD_CONST,5,11
WRITE_MEM,5,300
LOAD_CONST,5,22
WRITE_MEM,5,301
LOAD_CONST,5,33
WRITE_MEM,5,302

LOAD_CONST,0,300

READ_MEM,0,2,0
WRITE_MEM,2,400

READ_MEM,0,3,1
WRITE_MEM,3,401

READ_MEM,0,4,2
WRITE_MEM,4,402
"""
    }

    if example_name in examples:
        return jsonify({"success": True, "csv": examples[example_name]})
    else:
        return jsonify({"success": False, "error": "Example not found"})


def start():
    app.run(debug=True, host='0.0.0.0', port=5000)
