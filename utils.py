import hashlib


def md5(psw):
    md5_hash = hashlib.md5()
    md5_hash.update(psw.encode('utf-8'))
    return md5_hash.hexdigest()
