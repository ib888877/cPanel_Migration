# cpanel_transfer.py

import os
import paramiko
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging setup
debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

log_file = 'general.log'
logging.basicConfig(
    level=logging.DEBUG if debug_mode else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# SSH configuration
SOURCE_HOST = os.getenv("SOURCE_HOST")
SOURCE_PORT = int(os.getenv("SOURCE_PORT", 22))
SOURCE_USER = os.getenv("SOURCE_USER")
SOURCE_PASS = os.getenv("SOURCE_PASSWORD")

TARGET_HOST = os.getenv("TARGET_HOST")
TARGET_PORT = int(os.getenv("TARGET_PORT", 22))
TARGET_USER = os.getenv("TARGET_USER")
TARGET_PASS = os.getenv("TARGET_PASSWORD")

TRANSFER_WEBSITE = os.getenv("TRANSFER_WEBSITE", "false").lower() == "true"
TRANSFER_MAIL = os.getenv("TRANSFER_MAIL", "false").lower() == "true"
TRANSFER_DATABASE = os.getenv("TRANSFER_DATABASE", "false").lower() == "true"

DB_NAME_SRC = os.getenv("DB_NAME_SRC")
DB_USER_SRC = os.getenv("DB_USER_SRC")
DB_PASS_SRC = os.getenv("DB_PASS_SRC")

DB_NAME_TGT = os.getenv("DB_NAME_TGT")
DB_USER_TGT = os.getenv("DB_USER_TGT")
DB_PASS_TGT = os.getenv("DB_PASS_TGT")


def create_ssh_client_with_password(host, port, username, password):
    logging.info(f"Connecting to {username}@{host}:{port} with password auth")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=username, password=password)
    logging.info(f"Successfully connected to {host}")
    return ssh


def get_home_path(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command("pwd")
    home = stdout.read().decode().strip()
    logging.debug(f"Resolved remote home directory as: {home}")
    return home


def stream_tar_between_servers(ssh_src, ssh_tgt, src_path, tgt_path, folder_name):
    logging.info(f"Streaming folder '{folder_name}' from {src_path} to {tgt_path}")

    tar_create_cmd = f"tar czf - -C {src_path} {folder_name}"
    tar_extract_cmd = f"mkdir -p {tgt_path} && tar xzf - -C {tgt_path}"

    logging.debug(f"Source command: {tar_create_cmd}")
    logging.debug(f"Target command: {tar_extract_cmd}")

    if dry_run:
        logging.info("[DRY RUN] Commands printed but not executed.")
        return

    src_stdin, src_stdout, src_stderr = ssh_src.exec_command(tar_create_cmd)
    tgt_stdin, tgt_stdout, tgt_stderr = ssh_tgt.exec_command(tar_extract_cmd)

    try:
        transferred_bytes = 0
        chunk_size = 32768
        while True:
            data = src_stdout.channel.recv(chunk_size)
            if not data:
                break
            transferred_bytes += len(data)
            tgt_stdin.write(data)
            tgt_stdin.flush()
            logging.debug(f"Transferred {transferred_bytes / 1024:.2f} KB")

        tgt_stdin.close()
        exit_status_src = src_stdout.channel.recv_exit_status()
        exit_status_tgt = tgt_stdout.channel.recv_exit_status()

        if exit_status_src != 0:
            err = src_stderr.read().decode()
            logging.error(f"Source tar command failed: {err}")
        if exit_status_tgt != 0:
            err = tgt_stderr.read().decode()
            logging.error(f"Target tar command failed: {err}")

        if exit_status_src == 0 and exit_status_tgt == 0:
            logging.info(f"SUCCESS: Transferred folder '{folder_name}'")
        else:
            logging.error(f"FAILURE: Error transferring folder '{folder_name}'")

    except Exception as e:
        logging.exception(f"Exception during folder transfer '{folder_name}': {e}")


def transfer_folders(ssh_src, ssh_tgt, sub_path, folder_type):
    logging.info(f"Preparing to transfer {folder_type} folders from '{sub_path}'")

    src_home = get_home_path(ssh_src)
    tgt_home = get_home_path(ssh_tgt)

    folder_src = f"{src_home}/{sub_path}"
    folder_tgt = f"{tgt_home}/{sub_path}"

    sftp_src = ssh_src.open_sftp()
    try:
        sftp_src.chdir(folder_src)
    except IOError:
        logging.warning(f"Source path {folder_src} does not exist. Skipping {folder_type}.")
        sftp_src.close()
        return

    dirs = sftp_src.listdir()
    logging.info(f"Found {len(dirs)} folders to transfer in '{folder_src}'")

    for i, directory in enumerate(dirs, 1):
        logging.info(f"[{i}/{len(dirs)}] Transferring {folder_type} folder: {directory}")
        stream_tar_between_servers(ssh_src, ssh_tgt, folder_src, folder_tgt, directory)

    sftp_src.close()


def main():
    logging.info("Starting cPanel transfer script")

    ssh_src = create_ssh_client_with_password(SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS)
    ssh_tgt = create_ssh_client_with_password(TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS)

    if TRANSFER_WEBSITE:
        logging.info("Initiating WEBSITE transfer...")
        transfer_folders(ssh_src, ssh_tgt, "public_html", "public_html")

    if TRANSFER_MAIL:
        logging.info("Initiating MAIL transfer...")
        transfer_folders(ssh_src, ssh_tgt, "mail", "mail")

    if TRANSFER_DATABASE:
        logging.warning("Database transfer feature is not implemented yet.")

    ssh_src.close()
    ssh_tgt.close()
    logging.info("Transfer process completed.")


if __name__ == '__main__':
    main()
