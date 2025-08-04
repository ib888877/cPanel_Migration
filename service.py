import logging
import paramiko
import os
import time
from paramiko import RSAKey

# Logging setup
log_file = 'general.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)


def generate_RSA_key():
    # 1) Generate 2048-bit RSA private key
    key = RSAKey.generate(bits=2048)

    # 2) Save private key
    private_path = 'id_rsa'
    with open(private_path, 'w') as priv_file:
        key.write_private_key(priv_file)

    # 3) Save public key
    pub_path = private_path + '.pub'
    with open(pub_path, 'w') as pub_file:
        pub_file.write(f"{key.get_name()} {key.get_base64()}\n")

generate_RSA_key()

def get_home_path(ssh):
    home = run_command(ssh, "pwd")
    logging.debug(f"Resolved remote home directory as: {home}")
    return home


def create_ssh_client(host, port, user, passwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=passwd)
    return client


def run_command(ssh, command):
    logging.info(f"Command: {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    logging.info(f"Command exit_status: {exit_status}")
    out = stdout.read().decode().strip()
    logging.info(f"Command stdout: {out}")
    err = stderr.read().decode().strip()
    logging.info(f"Command err: {command}")
    if exit_status != 0:
        raise Exception(f"SCP command failed: {err}")
    
    return out


def compress_folder(ssh, source_path, tmp_src):
    cmd = f"tar czf {tmp_src} -C {source_path} ."
    run_command(ssh, cmd)
    logging.info(f"Compression complete: {tmp_src}")


def extract_tar_on_target(ssh, archive_path, extract_to):
    # cmd = f"mkdir -p {extract_to} && tar xzf {archive_path} -C {extract_to}"
    cmd = f"tar xzf {archive_path} -C {extract_to}"
    logging.info(f"Extracting archive")
    run_command(ssh, cmd)
    logging.info("Extraction complete")


def remove_file(ssh, file_path):
    cmd = f"rm -f {file_path}"
    logging.info(f"Removing file")
    run_command(ssh, cmd)
    logging.info("File removed")


def transfer_directory(
        SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS,
        TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS,
        path,folder_name):
    logging.info(f"--- {path}/{folder_name} Transfer Start ---")

    ssh_src = create_ssh_client(SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS)
    ssh_tgt = create_ssh_client(TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS)
    sftp_src = ssh_src.open_sftp()
    sftp_tgt = ssh_tgt.open_sftp()

    src_home = get_home_path(ssh_src)
    tgt_home = get_home_path(ssh_tgt)
    folder_src = f"{src_home}/{path}/{folder_name}"
    tmp_src = f"{src_home}/tmp/{folder_name}.tar.gz"
    folder_tgt = f"{tgt_home}/{path}/{folder_name}"
    tmp_tgt = f"{tgt_home}/tmp/{folder_name}.tar.gz"

    compress_folder(ssh_src, folder_src, tmp_src)

    #Check/create key on source server
    priv_key_path, pub_key_path = check_or_create_key(ssh_src, src_home)
    logging.info(f"priv_key_path:{priv_key_path}")
    logging.info(f"pub_key_path:{pub_key_path}")

    #Read the public key from source server
    with sftp_src.open(pub_key_path, 'r') as f:
        pub_key = f.read().decode()
    sftp_src.close()

    #Append the source public key to target's authorized_keys
    append_pubkey_to_target(ssh_tgt, pub_key)

    # Build scp command to run on source server (which initiates transfer)
    scp_cmd = f'scp -P {TARGET_PORT} -i {priv_key_path} {tmp_src} {TARGET_USER}@{TARGET_HOST}:{tmp_tgt}'
    out = run_command(ssh_src, scp_cmd)

    # Build scp command to run on source server (which initiates transfer)

    #Check/create key on source server
    # priv_key_path, pub_key_path = check_or_create_key(ssh_tgt, tgt_home)
    # logging.info(f"priv_key_path:{priv_key_path}")
    # logging.info(f"pub_key_path:{pub_key_path}")

    # #Read the public key from source server
    # with sftp_tgt.open(pub_key_path, 'r') as f:
    #     pub_key = f.read().decode()
    # sftp_tgt.close()

    # #Append the source public key to target's authorized_keys
    # append_pubkey_to_target(ssh_src, pub_key)

    # scp_cmd = f'scp -P {SOURCE_PORT} -i {priv_key_path} {SOURCE_USER}@{SOURCE_HOST}:{tmp_src} {tmp_tgt}'

    # print(f"Running file transfer on source server:\n{scp_cmd}")
    # exit_status, out, err = run_command(ssh_tgt, scp_cmd)




    extract_tar_on_target(ssh_tgt, tmp_tgt, folder_tgt)
    # remove_file(ssh_src, tmp_src)
    # remove_file(ssh_tgt, tmp_tgt)

    sftp_src.close()
    sftp_tgt.close()
    ssh_src.close()
    ssh_tgt.close()

    logging.info(f"--- {path}/{folder_name} Transfer Complete ---")


def check_or_create_key(ssh, home_path):
    key_path = f'{home_path}/.ssh/id_rsa'
    # Check if private key exists
    cmd_check = f'test -f {key_path} && echo EXISTS || echo MISSING'
    out= run_command(ssh, cmd_check)
    if 'EXISTS' in out:
        print(f"Key {key_path} exists.")
        return key_path, key_path + '.pub'
    # Generate key if missing
    print("Generating SSH key pair on remote server...")
    run_command(ssh, f'ssh-keygen -t rsa -b 2048 -N "" -f {key_path} <<< y >/dev/null 2>&1')
    time.sleep(1)  # wait a moment
    return key_path, key_path + '.pub'

def read_remote_file(ssh, remote_path):
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote_path, 'r') as f:
            content = f.read().decode()
    except IOError:
        content = None
    sftp.close()
    return content

def append_pubkey_to_target(ssh_target, pubkey):
    run_command(ssh_target, 'mkdir -p ~/.ssh && chmod 700 ~/.ssh')
    # Check if key already exists in authorized_keys
    authorized_keys = read_remote_file(ssh_target, '~/.ssh/authorized_keys')
    if authorized_keys and pubkey.strip() in authorized_keys:
        print("Public key already in authorized_keys on target.")
        return
    # Append the key
    run_command(ssh_target, f'echo "{pubkey.strip()}" >> ~/.ssh/authorized_keys')
    run_command(ssh_target, 'chmod 600 ~/.ssh/authorized_keys')
    print("Public key appended to target authorized_keys.")