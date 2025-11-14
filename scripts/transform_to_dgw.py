import os
import pandas as pd
import yaml
from openpyxl import load_workbook

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
    templates = [f for f in os.listdir(TEMPLATES_DIR) if f.lower().endswith(".xlsx")]

    if not incoming_files:
        print("⚠️ Nenhum arquivo de origem encontrado.")
        return
    if not templates:
        print("⚠️ Nenhum template DGW encontrado.")
        return

    for file in incoming_files:
        input_path = os.path.join(INCOMING_DIR, file)
        mapping_file = detect_mapping_file(file)
        mapping_path = os.path.join(CONFIG_DIR, mapping_file)

        if not os.path.exists(mapping_path):
            print(f"❌ Mapeamento não encontrado: {mapping_file}")
            continue

        mapping = load_yaml(mapping_path)["mappings"]

        # --- encontrar template correspondente
        template_file = None
        for t in templates:
            if "03_hirestack" in file.lower() and "03_hirestack" in t.lower():
                template_file = t
                break

        if not template_file:
            print(f"⚠️ Nenhum template correspondente ao arquivo {file}")
            continue

        template_path = os.path.join(TEMPLATES_DIR, template_file)
        print(f"\n➡️ Convertendo: {file}")
        print(f"   ↳ Template: {template_file}")
        print(f"   ↳ Mapping:  {mapping_file}")

        # carregar lista de abas válidas
        src_sheets = get_valid_sheets(input_path)
        tmpl_sheets = get_valid_sheets(template_path)

        # copiar workbook do template
        output_path = os.path.join(OUTPUT_DIR, f"{file.replace('.xlsx','')}_DGW_ready.xlsx")
        tmpl_wb = load_workbook(template_path)
        tmpl_wb.save(output_path)

        # reabrir para escrita
        out_wb = load_workbook(output_path)

        for sheet in tmpl_sheets:
            ws = out_wb[sheet]

            if sheet not in src_sheets:
                print(f"⚠️ Aba '{sheet}' não existe no origem — mantendo template vazio.")
                continue

            print(f"\n📄 Preenchendo aba: {sheet}")

            # 🔹 ORIGEM: cabeçalho na linha 2 → header=1
            src_df = pd.read_excel(input_path, sheet_name=sheet, header=1)
            src_df.columns = src_df.columns.astype(str).str.strip()

            #print("📌 Colunas no arquivo de origem:")
            #print(list(src_df.columns))

            #print("\n📌 Colunas esperadas no mapping (origem):")
            #for tgt, src in mapping.items():
            #    print(f"  - {src}  →  {tgt}")

            # 🔹 TEMPLATE DGW: cabeçalho real na linha 6
            header_row = 6
            template_headers = [
                (cell.value or "").strip() if isinstance(cell.value, str) else cell.value
                for cell in ws[header_row]
            ]
            header_index = {h: i for i, h in enumerate(template_headers) if h}

            # dados começam na linha 7
            start_row = 7

            for r_index, (_, row) in enumerate(src_df.iterrows()):
                # pula linhas totalmente vazias
                if row.isna().all():
                    continue

                excel_row = start_row + r_index

                for tgt_col, src_col in mapping.items():
                    # coluna de origem não existe → pula
                    if src_col not in src_df.columns:
                        continue

                    # coluna de destino não existe no template → pula
                    if tgt_col not in header_index:
                        continue

                    col_idx = header_index[tgt_col] + 1
                    value = row[src_col]
                    ws.cell(row=excel_row, column=col_idx, value=value)

        # salvar final
        out_wb.save(output_path)
        print(f"✅ DGW gerado com sucesso: {output_path}")


if __name__ == "__main__":
    transform_to_dgw()
