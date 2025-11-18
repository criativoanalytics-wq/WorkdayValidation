import os
import sys
import time
from datetime import datetime
from termcolor import colored

# =============================================================
# ⚙️ Base directory configuration
# =============================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates_dgw")
CURATED_DIR = os.path.join(DATA_DIR, "curated")

# =============================================================
# 🔧 Utility functions
# =============================================================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_header(title):
    clear_screen()
    print(colored("=" * 70, "blue"))
    print(colored(f" Workday DGW Orchestration Menu — {title} ", "cyan", attrs=["bold"]))
    print(colored("=" * 70, "blue"))

# =============================================================
# 🧩 Main orchestration functions
# =============================================================
def transform_templates():
    print_header("Template → DGW Transformation")
    from transform_to_dgw import transform_to_dgw

    # Confere se há templates
    if not os.path.exists(TEMPLATES_DIR):
        print(colored(f"❌ No template folder found at {TEMPLATES_DIR}", "red"))
        input("\nPress Enter to return...")
        return

    print(colored("🧩 Starting legacy → DGW transformation based on incoming files...\n", "cyan"))

    os.makedirs(CURATED_DIR, exist_ok=True)

    try:
        # ✅ Apenas UMA chamada — o transform_to_dgw processa todos os arquivos incoming
        transform_to_dgw()
    except Exception as e:
        print(colored(f"⚠️ Error during transformation: {e}", "red"))

    print(colored("\n✅ Transformation completed!", "green"))
    input("\nPress Enter to return to the menu...")


def validate_dgws():
    print_header("DGW Validation")
    from validate_all import main as validate_main

    print(colored("🔍 Running DGW validation...\n", "cyan"))
    validate_main()
    print(colored("\n✅ Validation completed. HTML dashboard saved in /outputs/", "green"))
    input("\nPress Enter to return to the menu...")

def run_full_pipeline():
    print_header("Full Pipeline (Transform + Validate + Dashboard)")
    from transform_to_dgw import transform_to_dgw
    from validate_all import main as validate_main

    print(colored("🧩 Running full pipeline...\n", "cyan"))
    time.sleep(1)

    # 1️⃣ Transform
    print(colored("➡️ Step 1/2: Transforming templates...", "yellow"))
    transform_to_dgw()

    # 2️⃣ Validate
    print(colored("➡️ Step 2/2: Validating generated DGWs...", "yellow"))
    validate_main()

    print(colored("\n✅ Full pipeline completed successfully!", "green"))
    input("\nPress Enter to return to the menu...")

def clear_outputs():
    print_header("Clear Outputs")
    if not os.path.exists(OUTPUT_DIR):
        print(colored("No output folder found.", "yellow"))
        input("\nPress Enter to return...")
        return
    for folder in ["failures", "previews"]:
        path = os.path.join(OUTPUT_DIR, folder)
        if os.path.exists(path):
            for f in os.listdir(path):
                os.remove(os.path.join(path, f))
    print(colored("🧹 Outputs cleaned successfully.", "green"))
    input("\nPress Enter to return...")

# =============================================================
# 🏁 Main menu
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

        choice = input(colored("Choose an option: ", "yellow")).strip()

        if choice == "1":
            from sftp_downloader import download_from_sftp
            download_from_sftp()
        elif choice == "2":
            transform_templates()
        elif choice == "3":
            validate_dgws()
        elif choice == "4":
            run_full_pipeline()  # may include the download
        elif choice == "5":
            clear_outputs()
        elif choice == "0":
            break

# =============================================================
# 🚀 Execution
# =============================================================
if __name__ == "__main__":
    main_menu()
