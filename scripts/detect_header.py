import pandas as pd
import re

def detect_dgw_header(file_path: str, sheet_name: str = 0, max_scan: int = 15):
    """
    Detecta automaticamente o header do DGW baseado na linha de 'Required'/'Optional'.
    Retorna o índice (base 0) da linha onde os nomes de colunas começam.
    """
    df_preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=max_scan)

    for i, row in df_preview.iterrows():
        row_str = " ".join(str(x).strip().lower() for x in row if pd.notna(x))
        if re.search(r"\b(required|optional)\b", row_str):
            print(f"📘 Linha de obrigatoriedade detectada (linha {i+1}). Cabeçalho será linha {i+2}.")
            return i + 1

    # fallback: heurística genérica
    for i, row in df_preview.iterrows():
        non_nulls = [str(x).strip() for x in row if pd.notna(x)]
        if len(non_nulls) >= 3 and any(re.search(r"(id|date|reason|type|code)", str(x), re.I) for x in non_nulls):
            print(f"📘 Header detectado na linha {i+1}: {non_nulls[:5]}")
            return i
    print("⚠️ Nenhum header encontrado, assumindo linha 0.")
    return 0


def read_with_auto_header(file_path: str, sheet_name: str = 0):
    header_row = detect_dgw_header(file_path, sheet_name)
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    print(f"✅ Colunas detectadas: {list(df.columns)}")
    return df
