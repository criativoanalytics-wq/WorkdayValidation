import os
from validate_all import validate_dgw

if __name__ == "__main__":
    input_path = "data/curated/DGW_HCM_03_HireStack_ready.xlsx"

    if not os.path.exists(input_path):
        print(f"❌ Arquivo não encontrado: {input_path}")
    else:
        print(f"🔍 Validando DGW transformado: {input_path}")
        results = validate_dgw(input_path)
        print("✅ Validação concluída!")
        for r in results:
            print(f" - {r['Sheet']}: {r['Success %']}% sucesso ({r['Failed']} falhas)")
