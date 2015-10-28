LOCAL_DOWNLOAD_DIR = "/tmp/"
DOWNLOAD_PROGRESS = True

# Data for cloud-init

META_DATA =  """instance-id: iid-123456
local-hostname: %s
"""
USER_DATA = """#cloud-config
password: %s
chpasswd: { expire: False }
ssh_pwauth: True
""" 
ATOMIC_USER_DATA = """#cloud-config
password: %s
chpasswd: { expire: False }
ssh_pwauth: True
""" 
