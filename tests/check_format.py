import os

fname = "zalo_export.zip"
with open(fname, 'rb') as f:
    header = f.read(16)

print("File header (hex):", header.hex())
print("File header (repr):", repr(header))
print("File size:", round(os.path.getsize(fname)/1024/1024, 1), "MB")

if header[:4] == b'PK\x03\x04':
    print("=> Standard ZIP")
elif header[:4] == b'PK\x05\x06':
    print("=> Empty ZIP")
elif header[:3] == b'\x1f\x8b\x08':
    print("=> GZIP / tar.gz")
elif header[:6] == b'7z\xbc\xaf\x27\x1c':
    print("=> 7-Zip")
elif header[:4] == b'Rar!':
    print("=> RAR")
elif header[:2] == b'BZ':
    print("=> BZ2")
else:
    print("=> Unknown format")
