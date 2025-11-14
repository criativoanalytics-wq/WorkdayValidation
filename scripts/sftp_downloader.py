import os
import paramiko
import yaml
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "sftp_config.yaml")

def download_from_sftp():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)["sftp"]

    remote_path = config["remote_path"]
    local_path = os.path.join(BASE_DIR, config["local_path"])

    os.makedirs(local_path, exist_ok=True)

    print(f"🔐 Conectando ao servidor SFTP: {config['host']}...")
    transport = paramiko.Transport((config["host"], config["port"]))
    transport.connect(username=config["username"], password=config["password"])
    sftp = paramiko.SFTPClient.from_transport(transport)

    print(f"📂 Acessando diretório remoto: {remote_path}")
    files = sftp.listdir(remote_path)

    for file in files:
        if file.lower().endswith(".xlsx"):
            remote_file = os.path.join(remote_path, file)
            local_file = os.path.join(local_path, file)
            print(f"⬇️  Baixando {file} ...")
            sftp.get(remote_file, local_file)

    sftp.close()
    transport.close()
    print(f"✅ Download concluído. Arquivos salvos em {local_path}")
    return local_path

if __name__ == "__main__":
    download_from_sftp()
