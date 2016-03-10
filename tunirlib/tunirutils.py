
import os
import shutil
import paramiko
import subprocess
from tunirdocker import Result

def run(host='127.0.0.1', port=22, user='root',
                  password=None, command='/bin/true', bufsize=-1, key_filename='',
                  timeout=120, pkey=None):
    """
    Excecutes a command using paramiko and returns the result.
    :param host: Host to connect
    :param port: The port number
    :param user: The username of the system
    :param password: User password
    :param command: The command to run
    :param key_filename: SSH private key file.
    :param pkey: RSAKey if we want to login with a in-memory key
    :return:
    """
    print(host, port, user)
    port = int(port)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if password:
        client.connect(hostname=host, port=port,
            username=user, password=password, banner_timeout=10)
    elif key_filename:
        client.connect(hostname=host, port=port,
            username=user, key_filename=key_filename, banner_timeout=10)
    else:
        print('We have a key')
        client.connect(hostname=host, port=port,
                username=user, pkey=pkey, banner_timeout=10)
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.set_combine_stderr(True)
    chan.get_pty()
    chan.exec_command(command)
    stdout = chan.makefile('r', bufsize)
    stderr = chan.makefile_stderr('r', bufsize)
    stdout_text = stdout.read()
    stderr_text = stderr.read()
    out = Result(stdout_text)
    status = int(chan.recv_exit_status())
    client.close()
    out.return_code = status
    return out

def clean_tmp_dirs(dirs):
    "Removes the temporary directories"
    for path in dirs:
        if os.path.exists(path) and path.startswith('/tmp'):
            shutil.rmtree(path)

def system(cmd):
    """
    Runs a shell command, and returns the output, err, returncode

    :param cmd: The command to run.
    :return:  Tuple with (output, err, returncode).
    """
    ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    out, err = ret.communicate()
    returncode = ret.returncode
    return out, err, returncode