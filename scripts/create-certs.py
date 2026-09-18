"""Generate a LAN-only CA and server certificate. Never auto-install trust."""
import argparse
import ipaddress
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import rsa

parser=argparse.ArgumentParser();parser.add_argument('--host',action='append',required=True,help='Repeat for every LAN IP or DNS name');parser.add_argument('--output',type=Path,default=Path('data/certs'))
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if any((out/n).exists() for n in ('ca-key.pem','ca.pem','server-key.pem','server.pem')):parser.error('Certificate files already exist. Choose a new output directory to avoid replacing trust.')
now=datetime.now(timezone.utc)
ca_key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Compute Relay Demo LAN CA')])
ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True).sign(ca_key,hashes.SHA256()))
key=rsa.generate_private_key(public_exponent=65537,key_size=3072);names=[]
for host in list(dict.fromkeys([*args.host,'localhost','127.0.0.1'])):
    try:names.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:names.append(x509.DNSName(host))
cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,args.host[0])])).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=120)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName(names),critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(ca_key,hashes.SHA256()))
for filename,value in [('ca-key.pem',ca_key),('server-key.pem',key)]:
    path=out/filename;path.write_bytes(value.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));path.chmod(0o600)
for filename,value in [('ca.pem',ca),('server.pem',cert)]:
    (out/filename).write_bytes(value.public_bytes(serialization.Encoding.PEM))
print('Certificates created. Share ca.pem only; keep both private keys on the central computer.')
