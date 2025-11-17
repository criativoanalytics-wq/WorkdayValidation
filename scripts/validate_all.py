import os
import yaml
import pandas as pd
import openpyxl
from datetime import datetime
from great_expectations.dataset import PandasDataset

# =============================================================================
# Caminhos base
# =============================================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data/curated")
CONFIG_FILE = os.path.join(BASE_DIR, "config", "field_mappings.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "previews")
FAILS_DIR = os.path.join(OUTPUT_DIR, "failures")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(FAILS_DIR, exist_ok=True)

# =============================================================================
# Configurações
# =============================================================================
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
ALIASES = CONFIG.get("aliases", {})

DEBUG_MODE = True  # altere para False se não quiser gerar previews


def get_col(df, key):
    """Retorna o nome real da coluna a partir do alias configurado."""
    for name in ALIASES.get(key, []):
        if name in df.columns:
            return name
    return None


def detect_type(file_path):
    """Identifica o tipo de DGW com base no nome do arquivo."""
    filename = os.path.basename(file_path).lower()
    if "hire" in filename:
        return "HireStack"
    elif "personalcontact" in filename or "contactinfo" in filename:
        return "PersonalContactInfo"
    elif "compensation" in filename:
        return "Compensation"
    elif "address" in filename:
        return "Address"
    elif "organization" in filename:
        return "Organization"
    elif "job" in filename:
        return "JobData"
    else:
        return "Generic"


def get_data_sheets(file_path):
    """Retorna uma lista de abas válidas (ignora abas cujo nome começa com '>')."""
    wb = openpyxl.load_workbook(file_path, read_only=True)
    valid_sheets = [s for s in wb.sheetnames if not s.strip().startswith(">")]
    wb.close()
    return valid_sheets



# =============================================================================
# Validação
# =============================================================================
def validate_dgw(file_path):
    """
    Executa a validação completa de todas as abas válidas de um arquivo DGW.
    Ignora abas que começam com '>' e utiliza a linha 6 como cabeçalho.
    Retorna uma lista de resultados (um por aba).
    """
    # Detecta tipo de DGW
    dgw_type = detect_type(file_path)
    valid_sheets = []
    try:
        wb = openpyxl.load_workbook(file_path, read_only=True)
        valid_sheets = [s for s in wb.sheetnames if not s.strip().startswith(">")]
        wb.close()
    except Exception as e:
        print(f"⚠️ Error opening workbook {file_path}: {e}")
        valid_sheets = []

    if not valid_sheets:
        print(f"⚠️ No valid tabs found in {file_path}")
        return []

    all_results = []

    for sheet_name in valid_sheets:
        print(f"\n➡️  Reading {os.path.basename(file_path)} → aba '{sheet_name}' (Header: line 6)")

        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=5)
        except Exception as e:
            print(f"❌ Error reading tab '{sheet_name}': {e}")
            all_results.append({
                "File": os.path.basename(file_path),
                "Sheet": sheet_name,
                "Type": dgw_type,
                "Total Checks": 0,
                "Failed": 0,
                "Success %": 0,
                "Error": str(e),
                "Fail HTML": ""
            })
            continue

        #print(f"Columns detected: {list(df.columns)}")

        # Preview opcional
        if DEBUG_MODE:
            preview_path = os.path.join(PREVIEW_DIR, f"{os.path.basename(file_path)}_{sheet_name}_preview.csv")
            df.head(10).to_csv(preview_path, index=False)
            print(f"🧩 Preview saved in: {preview_path}")

        # Ajuste de formato de data
        #hire_col = get_col(df, "hire_date")
        #if hire_col in df.columns:
        #    df[hire_col] = df[hire_col].astype(str)

        # Cria dataset GE
        ge_df = PandasDataset(df)

        # =========================================================
        # 🔎 Regras genéricas
        # =========================================================
        if get_col(df, "country_code"):
            ge_df.expect_column_values_to_match_regex(get_col(df, "country_code"), r"^[A-Z]{3}$")
        if get_col(df, "currency_code"):
            ge_df.expect_column_values_to_match_regex(get_col(df, "currency_code"), r"^[A-Z]{3}$")

        # =========================================================
        # 🔎 Regras específicas por tipo de DGW
        # =========================================================
        if dgw_type == "HireStack":
            emp = get_col(df, "employee_id")
            hire = get_col(df, "hire_date")
            etype = get_col(df, "employee_type")
            position_number = get_col(df, "position_number")

            # Cria lista para falhas manuais (será fundida a 'details' depois)
            manual_failures = []

            # 1) Employee ID: não nulo  (vai aparecer agora)
            if emp:
                ge_df.expect_column_values_to_not_be_null(emp)

            # 2) Datas: normalização + 2 regras (vazio e formato)
            if hire:
                try:
                    norm_col = "_norm_hire_date"

                    # Força leitura textual, preservando formatos originais
                    raw_values = df[hire].apply(lambda x: str(x).strip() if pd.notna(x) else "")

                    # Remove o sufixo "00:00:00" se vier de células datetime
                    cleaned = raw_values.str.replace(r"\s*00:00:00(\+00:00)?$", "", regex=True)

                    # 1️⃣ Marca vazios
                    is_empty = cleaned.eq("") | cleaned.str.lower().isin(["nan", "nat", "none"])

                    # 2️⃣ Regex de formato correto (yyyy-mm-dd)
                    valid_regex = r"^(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"

                    # 3️⃣ Cria coluna normalizada
                    normalized = cleaned.copy()
                    normalized[is_empty] = pd.NA

                    # Anexa ao dataset GE
                    ge_df[norm_col] = normalized

                    # (a) Vazios → falha
                    ge_df.expect_column_values_to_not_be_null(norm_col)

                    # (b) Formato incorreto → falha
                    ge_df.expect_column_values_to_match_regex(
                        norm_col,
                        valid_regex,
                        result_format="COMPLETE",
                    )

                except Exception as e:
                    print(f"⚠️ Error validating date format in column '{hire}': {e}")

            # 3) Outras regras
            if etype:
                ge_df.expect_column_values_to_be_in_set(
                    etype, ["Permanent", "Temporary", "Intern", "Contractor"]
                )
            if position_number:
                ge_df.expect_column_values_to_not_be_null(position_number)


        elif dgw_type == "PersonalContactInfo":
            email = get_col(df, "email")
            phone = get_col(df, "phone")
            if email:
                ge_df.expect_column_values_to_match_regex(email, r"[^@]+@[^@]+\.[^@]+")
            if phone:
                ge_df.expect_column_values_to_match_regex(phone, r"^[\d\+\-\(\) ]{8,20}$")

        # =========================================================
        # 🧩 Executa as validações
        # =========================================================
        try:
            result = ge_df.validate(result_format="COMPLETE")
        except Exception as e:
            print(f"❌ Internal error during tab validation '{sheet_name}': {e}")
            result = {"results": [], "statistics": {"evaluated_expectations": 0}}
            all_results.append({
                "File": os.path.basename(file_path),
                "Sheet": sheet_name,
                "Type": dgw_type,
                "Total Checks": 0,
                "Failed": 0,
                "Success %": 0,
                "Error": f"Validation crash: {e}",
                "Fail HTML": f"<div class='fail-container'><b>Erro interno:</b> {e}</div>"
            })
            continue

            # Contagem mais segura de resultados
        total = len(result.get("results", []))
        failed = sum(1 for r in result["results"] if not r.get("success", False))
        if total > 0:
            success_rate = (1 - failed / total) * 100
        else:
            success_rate = 0  # Nenhuma regra avaliada = erro total
        success_rate = round(float(success_rate), 2)

        # =========================================================
        # 📋 Gera relatório detalhado de falhas (linha, coluna, valor, regra)
        # =========================================================
        details = []
        for r in result["results"]:
            if not r["success"]:
                rule_name = r["expectation_config"].get("expectation_type", "Unknown Rule")
                col = r["expectation_config"]["kwargs"].get("column", "N/A")
                # 🔁 Mostra o nome real da coluna no relatório
                if col == "_norm_hire_date":
                    col = hire
                unexpected_vals = (
                    r["result"].get("unexpected_list")
                    or r["result"].get("partial_unexpected_list")
                    or []
                )
                unexpected_idx = (
                    r["result"].get("unexpected_index_list")
                    or r["result"].get("partial_unexpected_index_list")
                    or []
                )
                for val, idx in zip(unexpected_vals, unexpected_idx):
                    details.append({
                        "Column": col,
                        "Row": idx + 7,
                        "Value": val,
                        "Rule": rule_name
                    })

        # =========================================================
        # 🧱 Monta HTML de falhas
        # =========================================================
        if details:
            df_details = pd.DataFrame(details)
            fail_path = os.path.join(FAILS_DIR, f"{os.path.basename(file_path)}_{sheet_name}_failures.csv")
            df_details.to_csv(fail_path, index=False, encoding="utf-8-sig")

            fail_html = df_details[["Column", "Row", "Value", "Rule"]].to_html(
                index=False, border=0, classes="fail-table", justify="center"
            )
            fail_html = fail_html.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")

            fail_html = f"""
            <div class="fail-container" style="margin-top:10px;">
                <h4 style='color:#b00000;margin:10px 0;'>Fault Details — Aba: {sheet_name}</h4>
                {fail_html}
            </div>
            """
            print(f"❌ Details of saved failures in: {fail_path}")
        else:
            fail_html = f"<div class='fail-container'><i>No errors reported in the tab {sheet_name}.</i></div>"
            print(f"✅ No detailed faults recorded in the tab {sheet_name}.")

        # =========================================================
        # ✅ Adiciona resultado da aba
        # =========================================================
        all_results.append({
            "File": os.path.basename(file_path),
            "Sheet": sheet_name,
            "Type": dgw_type,
            "Total Checks": total,
            "Failed": failed,
            "Success %": round(success_rate, 2),
            "Error": "",
            "Fail HTML": fail_html
        })

    return all_results

def build_progress_bar(res):
    """Gera a barra de progresso com cor e largura corrigidas."""
    success_rate = float(res["Success %"])
    failed = int(res["Failed"])

    # Define cores da barra de progresso de forma mais precisa
    if res["Total Checks"] == 0:
        color_class = "none"  # Nenhuma regra avaliada → cinza claro
    elif res["Failed"] == res["Total Checks"]:
        color_class = "error"  # Todas falharam → vermelho
    elif res["Success %"] == 100:
        color_class = "success"  # Todas passaram → verde
    elif res["Success %"] >= 80:
        color_class = "warning"  # Maioria passou → laranja
    else:
        color_class = "error"  # Caso padrão: falhas significativas

    # Largura mínima de 2% para mostrar cor mesmo em 0%
    bar_width = max(success_rate, 2)
    return f"<div class='progress'><div class='progress-bar {color_class}' style='width:{bar_width}%;'></div></div>"

# =============================================================================
# Execução principal
# =============================================================================
def main():

    all_results = []

    # ---------------------------------------------------------
    # Load all Excel files
    # ---------------------------------------------------------
    for file in os.listdir(DATA_DIR):
        if file.lower().endswith(".xlsx"):
            path = os.path.join(DATA_DIR, file)
            print(f"\n🔍 Validating: {file}")
            try:
                file_results = validate_dgw(path)
                all_results.extend(file_results)
            except Exception as e:
                all_results.append({
                    "File": file,
                    "Sheet": "",
                    "Type": "Error",
                    "Total Checks": 0,
                    "Failed": 0,
                    "Success %": 0,
                    "Error": str(e),
                    "Fail HTML": ""
                })

    if not all_results:
        print("⚠️ No .xlsx files were found in /data/")
        return

    # ---------------------------------------------------------
    # Detect which tabs must appear
    # ---------------------------------------------------------
    hire_exists = any(r["Type"] == "HireStack" for r in all_results)
    contact_exists = any(r["Type"] == "PersonalContactInfo" for r in all_results)

    hire_tab_html = "<div class='tab' id='hire-tab' onclick=\"showTab('hire')\">👷 HireStack</div>" if hire_exists else ""
    contact_tab_html = "<div class='tab' id='contact-tab' onclick=\"showTab('contact')\">📇 Contact Info</div>" if contact_exists else ""

    # ---------------------------------------------------------
    # HTML Start
    # ---------------------------------------------------------
    styled_html = f"""
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Workday DGW Validation Dashboard</title>

        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 40px;
                background-color: #f5f7fa;
            }}

            h1 {{
                color: #2A6592;
                margin-bottom: 5px;
            }}

            .tabs {{
                margin-top: 20px;
                display: flex;
                gap: 10px;
                border-bottom: 2px solid #ccc;
            }}

            .tab {{
                background: #e6f0ff;
                padding: 10px 18px;
                border-radius: 6px 6px 0 0;
                cursor: pointer;
                font-weight: bold;
                color: #2A6592;
            }}

            .tab.active {{
                background: #2A6592;
                color: white;
            }}

            .tab-content {{
                display: none;
                background: white;
                padding: 20px;
                border-radius: 0 0 6px 6px;
                border: 1px solid #ddd;
            }}

            .tab-content.active {{
                display: block;
            }}

            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 10px;
            }}

            th, td {{
                padding: 8px 12px;
                text-align: center;
                border-bottom: 1px solid #ddd;
            }}

            th {{
                background-color: #e6f0ff;
            }}

            .toggle-btn {{
                background: #2A6592;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
            }}

            .progress {{
                background:#eee;
                width:120px;
                height:14px;
                border-radius:4px;
                overflow:hidden;
                display:inline-block;
            }}

            .progress-bar {{
                height:14px;
            }}

            .success {{ background:#27ae60; }}
            .warning {{ background:#f39c12; }}
            .error {{ background:#c0392b; }}
        </style>

        <script>

            function toggleDetails(id) {{
                const c = document.getElementById(id);
                if (!c) return;
                c.style.display = (c.style.display === "none" || c.style.display === "") ? "block" : "none";
            }}

            function showTab(tabName) {{
                document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
                document.getElementById(tabName + "-tab").classList.add("active");
                document.getElementById(tabName).classList.add("active");
            }}

            // -------------------------------
            // SELECT-BASED FILTERING SYSTEM
            // -------------------------------
            function applyFilters() {{

                const fileValue = document.getElementById("filterFile").value;
                const sheetValue = document.getElementById("filterSheet").value;

                const rows = document.querySelectorAll("#all tbody tr");

                let visible = [];

                rows.forEach(row => {{

                    const isData = row.classList.contains("data-row");
                    const isDetail = row.classList.contains("detail-row");

                    if (isData) {{
                        const f = row.dataset.file;
                        const s = row.dataset.sheet;

                        const matchFile = (!fileValue || f === fileValue);
                        const matchSheet = (!sheetValue || s === sheetValue);

                        if (matchFile && matchSheet) {{
                            row.style.display = "table-row";

                            const next = row.nextElementSibling;
                            if (next && next.classList.contains("detail-row")) {{
                                next.style.display = "table-row";
                            }}

                            visible.push(row);

                        }} else {{
                            row.style.display = "none";

                            const next = row.nextElementSibling;
                            if (next && next.classList.contains("detail-row")) {{
                                next.style.display = "none";
                            }}
                        }}
                    }}
                }});

                // fix striping
                let idx = 0;
                const allRows = document.querySelectorAll("#all tbody tr.data-row:not([style*='display: none'])");
                allRows.forEach(row => {{
                    row.style.backgroundColor = (idx % 2 === 0) ? "#ffffff" : "#f7f7f7";
                    idx++;
                }});

            }}

            // Populate selects
            document.addEventListener("DOMContentLoaded", () => {{
                const rows = document.querySelectorAll("#all tbody tr.data-row");
                const fSel = document.getElementById("filterFile");
                const sSel = document.getElementById("filterSheet");

                const files = new Set();
                const sheets = new Set();

                rows.forEach(r => {{
                    files.add(r.dataset.file);
                    sheets.add(r.dataset.sheet);
                }});

                [...files].sort().forEach(f => {{
                    fSel.innerHTML += `<option value="${{f}}">${{f}}</option>`;
                }});

                [...sheets].sort().forEach(s => {{
                    sSel.innerHTML += `<option value="${{s}}">${{s}}</option>`;
                }});
            }});
        </script>

    </head>
    <body>

        <h1>Workday DGW Validation Dashboard</h1>
        <p>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="tabs">
            <div class="tab active" id="all-tab" onclick="showTab('all')">📊 All Files</div>
            {hire_tab_html}
            {contact_tab_html}
        </div>

        <!-- ALL FILES TAB -->
        <div id="all" class="tab-content active">
            <div style="margin-bottom: 15px; display: flex; gap: 20px; align-items: center;">
                <div>
                    <label><b>Filter by File:</b></label><br>
                    <select id="filterFile" onchange="applyFilters()" style="padding:5px; width:220px;">
                        <option value="">All</option>
                    </select>
                </div>

                <div>
                    <label><b>Filter by Sheet:</b></label><br>
                    <select id="filterSheet" onchange="applyFilters()" style="padding:5px; width:220px;">
                        <option value="">All</option>
                    </select>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>File</th><th>Sheet</th><th>Type</th>
                        <th>Total Checks</th><th>Failed</th><th>Success %</th>
                        <th>Progress</th><th>Error</th><th>Details</th>
                    </tr>
                </thead>
                <tbody>
    """

    # -----------------------------
    # ALL FILES ROWS
    # -----------------------------
    for i, res in enumerate(all_results):

        bar = build_progress_bar(res)
        btn = f"<button class='toggle-btn' onclick=\"toggleDetails('fail_{i}')\">Show/Hide</button>" if res["Fail HTML"] else ""

        # Linha principal
        styled_html += f"""
        <tr class="data-row"
            data-file="{res['File']}"
            data-sheet="{res['Sheet']}">
            <td>{res['File']}</td>
            <td>{res['Sheet']}</td>
            <td>{res['Type']}</td>
            <td>{res['Total Checks']}</td>
            <td>{res['Failed']}</td>
            <td>{res['Success %']}%</td>
            <td>{bar}</td>
            <td>{res.get('Error', '')}</td>
            <td>{btn}</td>
        </tr>"""

        # Linha de detalhes (agora class detail-row)
        if res["Fail HTML"]:
            styled_html += f"""
            <tr class='detail-row'>
                <td colspan='9'><div id='fail_{i}' style='display:none'>{res['Fail HTML']}</div></td>
            </tr>
            """

    styled_html += "</tbody></table></div>"

    # -----------------------------
    # HireStack Tab
    # -----------------------------
    if hire_exists:

        hire_rows = ""
        for i, res in enumerate(all_results):
            if res["Type"] == "HireStack":
                bar = build_progress_bar(res)
                btn = f"<button class='toggle-btn' onclick=\"toggleDetails('hire_fail_{i}')\">Show/Hide</button>" if res["Fail HTML"] else ""

                hire_rows += f"""
                <tr>
                    <td>{res['File']}</td>
                    <td>{res['Sheet']}</td>
                    <td>{res['Total Checks']}</td>
                    <td>{res['Failed']}</td>
                    <td>{res['Success %']}%</td>
                    <td>{bar}</td>
                    <td>{btn}</td>
                </tr>"""

                if res["Fail HTML"]:
                    hire_rows += f"""
                    <tr class='detail-row'>
                        <td colspan='7'><div id='hire_fail_{i}' style='display:none'>{res['Fail HTML']}</div></td>
                    </tr>
                    """

        styled_html += f"""
        <div id="hire" class="tab-content">
            <h3>📘 HireStack Files</h3>
            <table>
                <thead>
                    <tr>
                        <th>File</th><th>Sheet</th><th>Total Checks</th>
                        <th>Failed</th><th>Success %</th><th>Progress</th><th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {hire_rows}
                </tbody>
            </table>
        </div>
        """

    # -----------------------------
    # Contact Info Tab
    # -----------------------------
    if contact_exists:

        contact_rows = ""
        for i, res in enumerate(all_results):
            if res["Type"] == "PersonalContactInfo":
                bar = build_progress_bar(res)
                btn = f"<button class='toggle-btn' onclick=\"toggleDetails('contact_fail_{i}')\">Show/Hide</button>" if res["Fail HTML"] else ""

                contact_rows += f"""
                <tr>
                    <td>{res['File']}</td>
                    <td>{res['Sheet']}</td>
                    <td>{res['Total Checks']}</td>
                    <td>{res['Failed']}</td>
                    <td>{res['Success %']}%</td>
                    <td>{bar}</td>
                    <td>{btn}</td>
                </tr>"""

                if res["Fail HTML"]:
                    contact_rows += f"""
                    <tr class='detail-row'>
                        <td colspan='7'><div id='contact_fail_{i}' style='display:none'>{res['Fail HTML']}</div></td>
                    </tr>
                    """

        styled_html += f"""
        <div id="contact" class="tab-content">
            <h3>📇 Contact Info Files</h3>
            <table>
                <thead>
                    <tr>
                        <th>File</th><th>Sheet</th><th>Total Checks</th>
                        <th>Failed</th><th>Success %</th><th>Progress</th><th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {contact_rows}
                </tbody>
            </table>
        </div>
        """

    styled_html += "</body></html>"

    # SAVE HTML
    html_path = os.path.join(OUTPUT_DIR, "validation_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(styled_html)

    print("\n✅ Validation completed!")
    print(f"📊 Dashboard saved to: {html_path}")

if __name__ == "__main__":
    main()
