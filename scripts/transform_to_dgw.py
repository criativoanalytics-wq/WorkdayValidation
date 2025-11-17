import os
import pandas as pd
import yaml
from openpyxl import load_workbook
from collections import defaultdict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config", "mappings")
INCOMING_DIR = os.path.join(BASE_DIR, "data", "incoming")
TEMPLATES_DIR = os.path.join(BASE_DIR, "data", "templates_dgw")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "curated")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_mapping_file(filename: str) -> str:
    name = filename.lower()
    if "hire" in name:
        return "mapping_hire.yaml"
    elif "contact" in name:
        return "mapping_contact.yaml"
    elif "worker" in name:
        return "mapping_worker.yaml"
    elif "absence" in name:
        return "mapping_absence.yaml"
    elif "compensation" in name:
        return "mapping_compensation.yaml"
    else:
        return "mapping_generic.yaml"


def get_valid_sheets(path):
    xl = pd.ExcelFile(path)
    sheets = [s for s in xl.sheet_names if not s.strip().startswith(">")]
    xl.close()
    return sheets


def transform_to_dgw():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    incoming_files = [f for f in os.listdir(INCOMING_DIR) if f.lower().endswith(".xlsx")]
    template_files = [f for f in os.listdir(TEMPLATES_DIR) if f.lower().endswith(".xlsx")]

    if not incoming_files:
        print("⚠️ No source files found.")
        return
    if not template_files:
        print("⚠️ No DGW templates were found in the /templates_dgw folder.")
        return

    # 🔥 Considera apenas 1 template principal (o único que a pasta possui)
    template_path = os.path.join(TEMPLATES_DIR, template_files[0])
    print(f"📄 Template Loaded: {template_files[0]}")

    for file in incoming_files:

        print(f"\n➡️ Converting {file}...")

        input_path = os.path.join(INCOMING_DIR, file)
        mapping_file = detect_mapping_file(file)
        mapping_path = os.path.join(CONFIG_DIR, mapping_file)

        if not os.path.exists(mapping_path):
            print(f"❌ Mapping not found: {mapping_file}")
            continue

        mapping = load_yaml(mapping_path)["mappings"]

        # carregando template único
        tmpl_wb = load_workbook(template_path)
        output_path = os.path.join(OUTPUT_DIR, f"{file.replace('.xlsx','')}_DGW_ready.xlsx")
        tmpl_wb.save(output_path)

        out_wb = load_workbook(output_path)

        src_sheets = get_valid_sheets(input_path)
        tmpl_sheets = get_valid_sheets(template_path)

        for sheet in tmpl_sheets:

            ws = out_wb[sheet]

            if sheet not in src_sheets:
                print(f"⚠️ Sheet '{sheet}' does not exist in the legacy file — it will be left empty.")
                continue

            print(f"   📝 Filling in tab: {sheet}")

            # origem → header na linha 2
            src_df = pd.read_excel(
                input_path,
                sheet_name=sheet,
                header=1,
                keep_default_na=False,
                na_values=[]   # impede conversão de 'NA' → NaN
            )

            src_df.columns = src_df.columns.astype(str).str.strip()
            src_df = src_df.fillna("")  # garante que nunca apareçam NaN

            # cabeçalhos do template (linha 6)
            header_row = 6
            template_headers = [
                (cell.value.strip() if isinstance(cell.value, str) else cell.value)
                for cell in ws[header_row]
            ]

            # cada header → lista de posições (para duplicados)
            header_positions = defaultdict(list)
            for col_index, header in enumerate(template_headers):
                if header:
                    header_positions[header].append(col_index)

            start_row = 7

            for r_index, (_, row) in enumerate(src_df.iterrows()):
                if row.isna().all():
                    continue

                excel_row = start_row + r_index

                for tgt_col, src_col in mapping.items():

                    if src_col not in src_df.columns:
                        continue

                    if tgt_col not in header_positions:
                        continue

                    value = row[src_col]

                    # escrever em TODAS as colunas com mesmo header
                    for col_idx in header_positions[tgt_col]:
                        ws.cell(row=excel_row, column=col_idx + 1, value=value)

        out_wb.save(output_path)
        print(f"✅ DGW file ready: {output_path}")


if __name__ == "__main__":
    transform_to_dgw()
