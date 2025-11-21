import os
import sys
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
RULES_FILE = os.path.join(BASE_DIR, "config", "rules_global.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "previews")
FAILS_DIR = os.path.join(OUTPUT_DIR, "failures")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(FAILS_DIR, exist_ok=True)


# =============================================================================
# Load Global Rules
# =============================================================================
with open(RULES_FILE, "r", encoding="utf-8") as f:
    GLOBAL_RULES = yaml.safe_load(f)

DEBUG_MODE = True

def debug(msg):
    if DEBUG_MODE:
        print(msg)

# paleta simples sem depender de lib externa
COLOR = {
    "cyan": "\033[96m",
    "yellow": "\033[93m",
    "green": "\033[92m",
    "red": "\033[91m",
    "bold": "\033[1m",
    "end": "\033[0m"
}

def color(text, c):
    if DEBUG_MODE:
        return f"{COLOR[c]}{text}{COLOR['end']}"
    return text

def detect_type(file_path):
    filename = os.path.basename(file_path).lower()
    if "hire" in filename:
        return "HireStack"
    elif "contact" in filename:
        return "PersonalContactInfo"
    return "Generic"


def get_valid_sheets(file_path):
    wb = openpyxl.load_workbook(file_path, read_only=True)
    sheets = [s for s in wb.sheetnames if not s.strip().startswith(">")]
    wb.close()
    return sheets



# =============================================================================
# Função para aplicar regra GE dinamicamente
# =============================================================================
def apply_rule(ge_df, df, column_name, rule_obj):
    """
    rule_obj pode ser:
    - {rule: not_null}
    - {rule: regex, pattern: "..."}
    - {rule: allowed_set, values: [...]}
    """

    if rule_obj["rule"] == "not_null":
        ge_df.expect_column_values_to_not_be_null(column_name)

    elif rule_obj["rule"] == "regex":
        regex = rule_obj["pattern"]

        # Normaliza data antes de aplicar regex
        clean_col = f"_norm_{column_name.replace(' ', '_')}"
        raw = df[column_name].astype(str).str.replace(r"\s*00:00:00.*$", "", regex=True)

        normalized = raw.copy()
        normalized[normalized.isin(["nan", "None", "", "NaT"])] = pd.NA

        ge_df[clean_col] = normalized

        ge_df.expect_column_values_to_not_be_null(clean_col)
        ge_df.expect_column_values_to_match_regex(clean_col, regex)

    elif rule_obj["rule"] == "allowed_set":
        allowed = rule_obj["values"]
        ge_df.expect_column_values_to_be_in_set(column_name, allowed)



# =============================================================================
# Validação Principal
# =============================================================================
def get_col(df, yaml_column, aliases):
    """
    Localiza uma coluna real no dataframe baseada no nome do YAML ou aliases.
    - yaml_column: nome exato do arquivo global_rules.yaml
    - aliases: dicionário de alias carregado em field_mappings.yaml
    """
    # 1) Nome exato
    if yaml_column in df.columns:
        return yaml_column

    # 2) Aliases possíveis
    if yaml_column in aliases:
        for alias in aliases[yaml_column]:
            if alias in df.columns:
                return alias

    # 3) Não existe
    return None


def validate_dgw(file_path):
    """
    Versão FINAL com logs detalhados:
    - Usa regras globais (rules_global.yaml)
    - Usa get_col() para mapear alias → coluna real
    - Valida apenas colunas existentes
    - Logs aparecem apenas quando DEBUG_MODE = True
    """

    def debug(msg):
        if DEBUG_MODE:
            print(msg)

    # ---------------------------------------------------------
    # Load Global Rules
    # ---------------------------------------------------------
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            GLOBAL_RULES = yaml.safe_load(f)
        debug("\n📘 Global rules loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading YAML rules: {e}")
        return []

    # Load aliases (optional)
    aliases = {}
    alias_file = os.path.join(BASE_DIR, "config", "field_mappings.yaml")
    if os.path.exists(alias_file):
        with open(alias_file, "r", encoding="utf-8") as f:
            alias_yaml = yaml.safe_load(f)
            aliases = alias_yaml.get("aliases", {})

        debug(f"📘 Aliases loaded: {aliases}")
    else:
        debug("⚠️ No alias file found. Proceeding without aliases.")

    dgw_type = detect_type(file_path)

    # ---------------------------------------------------------
    # Load valid sheets
    # ---------------------------------------------------------
    valid_sheets = get_valid_sheets(file_path)
    if not valid_sheets:
        print(f"⚠️ No valid tabs found in {file_path}")
        return []

    debug(f"\n📄 Valid sheets detected: {valid_sheets}")

    all_results = []

    # ---------------------------------------------------------
    # Validate each sheet
    # ---------------------------------------------------------
    for sheet_name in valid_sheets:

        debug(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        debug(f"➡️ Validating sheet: {sheet_name}")
        debug(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=5)
            debug(f"📊 Columns detected: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading sheet {sheet_name}: {e}")
            continue

        if DEBUG_MODE:
            preview_path = os.path.join(
                PREVIEW_DIR,
                f"{os.path.basename(file_path)}_{sheet_name}_preview.csv"
            )
            df.head(20).to_csv(preview_path, index=False)
            debug(f"🧩 Preview saved: {preview_path}")

        ge_df = PandasDataset(df)
        failure_details = []
        total_checks = 0

        # ---------------------------------------------------------
        # Apply global rules
        # ---------------------------------------------------------
        debug("\n📌 Starting column rule validation...")

        for yaml_column, rule_set in GLOBAL_RULES.items():

            #debug(f"\n🔍 Checking YAML column: {yaml_column}")

            # Encontrar coluna real usando get_col()
            real_col = get_col(df, yaml_column, aliases)

            if not real_col:
                #debug(f"   ⚠️ Column not present in this sheet. Skipping.")
                continue

            debug(f"   ✔ Column found in Excel as: {real_col}")
            expectations = rule_set.get("expectations", [])
            debug(f"   ➤ Expectations: {expectations}")

            # -----------------------------
            # NOT NULL
            # -----------------------------
            if "expect_column_values_to_not_be_null" in expectations:
                debug(f"      • Applying NOT NULL")

                res = ge_df.expect_column_values_to_not_be_null(real_col)
                total_checks += 1

                if not res.success:
                    debug(f"        ❌ Not Null FAILED")
                    for idx in res.result.get("unexpected_index_list", []):
                        failure_details.append({
                            "Column": real_col,
                            "Row": idx + 7,
                            "Value": df.loc[idx, real_col],
                            "Rule": "not_null"
                        })
                else:
                    debug(f"        ✔ Not Null PASSED")

            # -----------------------------
            # REGEX
            # -----------------------------
            if "expect_column_values_to_match_regex" in expectations:
                pattern = rule_set.get("pattern")
                debug(f"      • Applying REGEX → {pattern}")

                res = ge_df.expect_column_values_to_match_regex(real_col, pattern)
                total_checks += 1

                if not res.success:
                    debug(f"        ❌ Regex FAILED")
                    for idx, val in zip(
                        res.result.get("unexpected_index_list", []),
                        res.result.get("unexpected_list", [])
                    ):
                        failure_details.append({
                            "Column": real_col,
                            "Row": idx + 7,
                            "Value": val,
                            "Rule": f"regex: {pattern}"
                        })
                else:
                    debug(f"        ✔ Regex PASSED")

            # -----------------------------
            # IN SET
            # -----------------------------
            if "expect_column_values_to_be_in_set" in expectations:
                allowed = rule_set.get("allowed_values", [])
                debug(f"      • Applying IN SET → {allowed}")

                res = ge_df.expect_column_values_to_be_in_set(real_col, allowed)
                total_checks += 1

                if not res.success:
                    debug(f"        ❌ In Set FAILED")
                    for idx, val in zip(
                        res.result.get("unexpected_index_list", []),
                        res.result.get("unexpected_list", [])
                    ):
                        failure_details.append({
                            "Column": real_col,
                            "Row": idx + 7,
                            "Value": val,
                            "Rule": f"in_set: {allowed}"
                        })
                else:
                    debug(f"        ✔ In Set PASSED")

        # ---------------------------------------------------------
        # Finalização da aba
        # ---------------------------------------------------------
        # Agora executamos a validação REAL do GE
        validation = ge_df.validate(result_format="COMPLETE")

        failed = 0
        failure_details = []

        for r in validation["results"]:
            if not r.get("success"):
                failed += 1

                rule_name = r["expectation_config"]["expectation_type"]
                col = r["expectation_config"]["kwargs"].get("column")

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
                    failure_details.append({
                        "Column": col,
                        "Row": idx + 7,
                        "Value": val,
                        "Rule": rule_name
                    })

        total_checks = len(validation["results"])
        success_rate = (1 - failed / total_checks) * 100 if total_checks > 0 else 100

        debug(f"\n📘 Finished sheet: {sheet_name}")
        debug(f"   ➤ Total checks: {total_checks}")
        debug(f"   ➤ Failures: {failed}")
        debug(f"   ➤ Success rate: {round(success_rate, 2)}%")

        if failed:
            df_fail = pd.DataFrame(failure_details)
            fail_path = os.path.join(
                FAILS_DIR,
                f"{os.path.basename(file_path)}_{sheet_name}_failures.csv"
            )
            df_fail.to_csv(fail_path, index=False, encoding="utf-8-sig")
            fail_html = df_fail.to_html(index=False, border=0)
            debug(f"   ❌ Failures saved to: {fail_path}")
        else:
            fail_html = "<i>No validation errors found.</i>"
            debug("   ✔ No failures.")

        all_results.append({
            "File": os.path.basename(file_path),
            "Sheet": sheet_name,
            "Type": dgw_type,
            "Total Checks": total_checks,
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
