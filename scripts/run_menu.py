import os
import sys
import time
from datetime import datetime
from termcolor import colored

# =============================================================
# ⚙️ Configuração de diretórios base
# =============================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates_dgw")
CURATED_DIR = os.path.join(DATA_DIR, "curated")

# =============================================================
# 🔧 Funções utilitárias
# =============================================================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_header(title):
    clear_screen()
    print(colored("=" * 70, "blue"))
    print(colored(f" Workday DGW Orchestration Menu — {title} ", "cyan", attrs=["bold"]))
    print(colored("=" * 70, "blue"))

# =============================================================
# 🧩 Funções principais de orquestração
# =============================================================
def transform_templates():
    print_header("Template → DGW Transformation")
    from transform_to_dgw import transform_to_dgw

    if not os.path.exists(TEMPLATES_DIR):
        print(colored(f"❌ Nenhuma pasta encontrada em {TEMPLATES_DIR}", "red"))
        input("\nPressione Enter para voltar...")
        return

    print(colored("🧩 Iniciando transformação de templates legados...\n", "cyan"))
    os.makedirs(CURATED_DIR, exist_ok=True)
    for file in os.listdir(TEMPLATES_DIR):
        if file.lower().endswith(".xlsx"):
            print(f"➡️ Convertendo {file}...")
            try:
                transform_to_dgw()
            except Exception as e:
                print(colored(f"⚠️ Falha ao transformar {file}: {e}", "red"))
    print(colored("\n✅ Transformação concluída!", "green"))
    input("\nPressione Enter para voltar ao menu...")

def validate_dgws():
    print_header("DGW Validation")
    from validate_all import main as validate_main

    print(colored("🔍 Executando validação de DGWs...\n", "cyan"))
    validate_main()
    print(colored("\n✅ Validação concluída. Dashboard HTML gerado em /outputs/", "green"))
    input("\nPressione Enter para voltar ao menu...")

def run_full_pipeline():
    print_header("Full Pipeline (Transform + Validate + Dashboard)")
    from transform_to_dgw import transform_to_dgw
    from validate_all import main as validate_main

    print(colored("🧩 Executando pipeline completo...\n", "cyan"))
    time.sleep(1)

    # 1️⃣ Transform
    print(colored("➡️ Etapa 1/2: Transformando templates...", "yellow"))
    transform_to_dgw()

    # 2️⃣ Validate
    print(colored("➡️ Etapa 2/2: Validando DGWs gerados...", "yellow"))
    validate_main()

    print(colored("\n✅ Pipeline completo finalizado com sucesso!", "green"))
    input("\nPressione Enter para voltar ao menu...")

def clear_outputs():
    print_header("Clear Outputs")
    if not os.path.exists(OUTPUT_DIR):
        print(colored("Nenhuma pasta de saída encontrada.", "yellow"))
        input("\nPressione Enter para voltar...")
        return
    for folder in ["failures", "previews"]:
        path = os.path.join(OUTPUT_DIR, folder)
        if os.path.exists(path):
            for f in os.listdir(path):
                os.remove(os.path.join(path, f))
    print(colored("🧹 Saídas limpas com sucesso.", "green"))
    input("\nPressione Enter para voltar...")

# =============================================================
# 🏁 Menu principal
# =============================================================
def main_menu():
    while True:
        clear_screen()
        print(colored("=" * 70, "blue"))
        print(colored("   🌐 Workday DGW Validation Orchestrator", "cyan", attrs=["bold"]))
        print(colored("=" * 70, "blue"))
        print()
        print("1️⃣  Download DGWs via SFTP")
        print("2️⃣  Transform templates → DGWs")
        print("3️⃣  Validate existing DGWs")
        print("4️⃣  Run Full Pipeline (SFTP + Transform + Validate + Dashboard)")
        print("5️⃣  Clear output folders")
        print("0️⃣  Exit")
        print()

        choice = input(colored("Escolha uma opção: ", "yellow")).strip()

        if choice == "1":
            from sftp_downloader import download_from_sftp
            download_from_sftp()
        elif choice == "2":
            transform_templates()
        elif choice == "3":
            validate_dgws()
        elif choice == "4":
            run_full_pipeline()  # pode incluir o download
        elif choice == "5":
            clear_outputs()
        elif choice == "0":
            break

# =============================================================
# 🚀 Execução
# =============================================================
if __name__ == "__main__":
    main_menu()
