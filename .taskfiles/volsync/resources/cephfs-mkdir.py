# Create a directory on the external CephFS without mounting it.
# Runs inside the rook-ceph-tools pod (libcephfs + admin keyring), fed on stdin:
#   kubectl exec -i deploy/rook-ceph-tools -- python3 - <path> < cephfs-mkdir.py
import sys

import cephfs

path = sys.argv[1]
if not path.startswith("/") or ".." in path.split("/"):
    sys.exit(f"refusing path {path!r}: must be absolute with no '..'")

fs = cephfs.LibCephFS(conffile="/etc/ceph/ceph.conf")
fs.mount(filesystem_name=b"cephfs")
try:
    try:
        fs.stat(path.encode())
        print(f"{path} already exists")
    except cephfs.ObjectNotFound:
        fs.mkdirs(path.encode(), 0o755)
        print(f"created {path}")
finally:
    fs.unmount()
    fs.shutdown()
