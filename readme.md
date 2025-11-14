# 🧾 Workday DGW Validation

Um validador automatizado de planilhas **DGW (Data Gathering Workbook)** do **Workday**, desenvolvido em **Python 3.11+** e integrado ao **Great Expectations**.  
O sistema realiza verificações de qualidade de dados em arquivos Excel (.xlsx), gera relatórios CSV e um **dashboard HTML interativo** para visualização dos resultados.

---

## 🚀 Funcionalidades Principais

✅ **Leitura automática das planilhas DGW**
- Detecta a aba correta (ignora abas que começam com `>`)
- Define a **linha 6** como cabeçalho fixo

🧠 **Identificação automática do tipo de DGW**
- Baseada no nome do arquivo (`HireStack`, `PersonalContactInfo`, `Compensation`, etc.)

🧩 **Validações automáticas via Great Expectations**
- Regras genéricas (ex: `country_code`, `currency_code`)
- Regras específicas para cada tipo (ex: HireStack, PersonalContactInfo)
- Armazena as falhas com linha, coluna, valor e regra quebrada

📊 **Dashboard HTML interativo**
- Abas de navegação:
  - “Todos os Arquivos”
  - “HireStack”
  - “Contact Info”
- Botões “Mostrar/Ocultar” para exibir falhas linha a linha
- Barras de progresso coloridas (verde, amarelo, vermelho) conforme taxa de sucesso

🗂️ **Geração automática de relatórios**
- `validation_summary.csv` → resumo geral da execução
- `validation_dashboard.html` → painel interativo
- `/failures/*.csv` → falhas detalhadas por arquivo

---

## 🧱 Estrutura de Pastas

WorkdayValidation/
│
├── config/
│ └── field_mappings.yaml # aliases e nomes esperados para colunas
│
├── data/
│ ├── DGW_HCM_02_PersonalContactInfo.xlsx
│ ├── DGW_HCM_03_HireStack.xlsx
│ └── ... (demais arquivos DGW)
│
├── outputs/
│ ├── previews/ # amostras CSV dos 10 primeiros registros
│ ├── failures/ # relatórios de falhas detalhadas
│ ├── validation_summary.csv # resumo geral
│ └── validation_dashboard.html # dashboard interativo
│
├── scripts/
│ ├── init_ge.py # inicializa estrutura base do GE
│ └── validate_all.py # script principal de validação
│
├── .venv/ # ambiente virtual Python (3.11+)
└── README.md

yaml
Copiar código

---

## ⚙️ Instalação

### 1️⃣ Criar ambiente virtual
```bash
python -m venv .venv
2️⃣ Ativar o ambiente
bash
Copiar código
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
3️⃣ Instalar dependências
bash
Copiar código
pip install pandas openpyxl pyyaml great_expectations
💡 Se quiser gerar o requirements.txt:

bash
Copiar código
pip freeze > requirements.txt
4️⃣ Inicializar o Great Expectations
bash
Copiar código
python scripts/init_ge.py
Saída esperada:

php-template
Copiar código
✅ Great Expectations project initialized successfully at: C:\Users\<user>\PycharmProjects\WorkdayValidation\great_expectations
▶️ Execução
Execute a validação principal:

bash
Copiar código
python scripts/validate_all.py
Exemplo de saída:

bash
Copiar código
🔍 Validating: DGW_HCM_02_PersonalContactInfo.xlsx
➡️  Lendo DGW_HCM_02_PersonalContactInfo.xlsx → aba 'Worker Name Data' (cabeçalho: linha 6)
Colunas detectadas: ['Worker ID', 'Worker Type', 'Country ISO Code', ...]
✅ Nenhuma falha detalhada registrada.

🔍 Validating: DGW_HCM_03_HireStack.xlsx
➡️  Lendo DGW_HCM_03_HireStack.xlsx → aba 'Hire Employee' (cabeçalho: linha 6)
Colunas detectadas: ['Employee ID', 'Hire Date', 'Employee Type', ...]
❌ Detalhes de falhas salvos em: outputs/failures/DGW_HCM_03_HireStack.xlsx_failures.csv

✅ Validação concluída com sucesso!
📄 CSV salvo em: outputs/validation_summary.csv
📊 Dashboard HTML: outputs/validation_dashboard.html
📊 Dashboard HTML
O arquivo outputs/validation_dashboard.html é o principal relatório interativo.
Ele contém três abas:

📁 Todos os Arquivos
Mostra todos os arquivos processados, com:

Nome e tipo de DGW

Total de verificações executadas

Falhas encontradas

Percentual de sucesso (%)

Barra de progresso colorida

Botão “Mostrar/Ocultar” para exibir as falhas detalhadas

👷 HireStack
Mostra apenas arquivos com tipo HireStack, incluindo:

Verificações de employee_id, hire_date e employee_type

Regras aplicadas e valores inválidos

🧑‍💼 Contact Info
Mostra apenas arquivos PersonalContactInfo, com validações de:

Formato de e-mail

Formato de telefone

📑 Estrutura do Relatório de Falhas
Cada arquivo com erro gera um CSV e um trecho HTML com o formato:

Column	Row	Value	Rule
Employee Type	7	Regular	expect_column_values_to_be_in_set
Hire Date	12	2024-13-01	expect_column_values_to_match_strftime_format

Esses dados também são exportados para:

bash
Copiar código
outputs/failures/<arquivo>_failures.csv
🧠 Regras Implementadas
🔹 Regras genéricas
Campo	Validação	Exemplo
country_code	3 letras maiúsculas (Regex ^[A-Z]{3}$)	BRA, USA
currency_code	3 letras maiúsculas (Regex ^[A-Z]{3}$)	BRL, USD

🔹 Regras de HireStack
Campo	Regra	Tipo de Validação
employee_id	Não pode ser nulo	expect_column_values_to_not_be_null
hire_date	Deve seguir o formato YYYY-MM-DD	expect_column_values_to_match_strftime_format
employee_type	Valor dentro do conjunto permitido	expect_column_values_to_be_in_set

🔹 Regras de PersonalContactInfo
Campo	Regra	Tipo de Validação
email	Deve ser um e-mail válido	expect_column_values_to_match_regex
phone	Deve conter apenas números, +, -, ou espaços	expect_column_values_to_match_regex

🧩 Próximas Melhorias
 Exibir descrição amigável das regras (ex: “Formato inválido de data” em vez de expect_column_values_to_match_strftime_format)

 Adicionar suporte a outros tipos (Compensation, Address, Organization, etc.)

 Incluir métricas adicionais (linhas processadas, tempo de execução)

 Adicionar exportação em formato .xlsx ou .pdf

 Integração com AIDA Data Quality Pipeline

💡 Dicas para Customização
Você pode adicionar novos tipos de DGW editando a função detect_type() em validate_all.py:

python
Copiar código
def detect_type(file_path):
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
    else:
        return "Generic"
🧾 Exemplo visual
Ao final da execução, o dashboard exibe um resumo com:

Abas navegáveis

Botões de expansão (“Mostrar/Ocultar”)

Tabelas de falhas com colunas: Column, Row, Value, Rule

Barra de sucesso colorida:

Cor	Significado
🟩 Verde	100% sucesso
🟧 Amarelo	80–99% sucesso
🟥 Vermelho	Abaixo de 80%

👨‍💻 Autor
Lucas Silva
Desenvolvimento e Data Quality – Integração Workday
📍 Blumenau, SC – 2025