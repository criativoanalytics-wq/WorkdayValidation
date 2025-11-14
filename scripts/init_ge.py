import os
from great_expectations.data_context.types.base import (
    DataContextConfig,
    FilesystemStoreBackendDefaults,
)
from great_expectations.data_context import BaseDataContext

# Caminhos básicos
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ge_dir = os.path.join(base_dir, "great_expectations")

# 1) Cria estrutura mínima de pastas
os.makedirs(ge_dir, exist_ok=True)

# 2) Define configuração de contexto mínima (usa backends locais em filesystem)
project_config = DataContextConfig(
    datasources={},
    store_backend_defaults=FilesystemStoreBackendDefaults(root_directory=ge_dir),
    anonymous_usage_statistics={"enabled": False},
)

# 3) Instancia o contexto e salva configuração
context = BaseDataContext(project_config)
context._save_project_config()

print(f"✅ Great Expectations project initialized successfully at: {ge_dir}")
