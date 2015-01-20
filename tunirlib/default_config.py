import os
import json

# url to the database server:
DB_URL = 'sqlite:////tmp/tunir_dev.sqlite'

if os.path.exists('./tunir.config'):
    with open('./tunir.config') as fobj:
        data = json.load(fobj)
        DB_URL = data['db_url']
elif os.path.exists('/etc/tunir.config'):
    with open('/etc/tunir.config') as fobj:
        data = json.load(fobj)
        DB_URL = data['db_url']


