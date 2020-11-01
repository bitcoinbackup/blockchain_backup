# See
#    The configuration file should be a valid Python source file with a python extension (e.g. gunicorn.conf.py).
#    https://docs.gunicorn.org/en/stable/configure.html

bind='127.0.0.1:8962'
timeout=75
daemon=True
user='user'
accesslog='/var/local/log/user/blockchain_backup.gunicorn.access.log'
errorlog='/var/local/log/user/blockchain_backup.gunicorn.error.log'
log_level='debug'
capture_output=True
max_requests=3
workers=1
