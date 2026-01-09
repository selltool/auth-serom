import base64
from nacl.public import PrivateKey, SealedBox
from utils import decrypt_ciphertext_b64
import os

def test_decryption():
    print("Generating temporary keypair...")
    sk = PrivateKey.generate()
    pk = sk.public_key
    
    sk_b64 = base64.b64encode(sk.encode()).decode('utf-8')
    
    print(f"Private Key (B64): {sk_b64}")
    
    message = b'{"SN": "TEST-SN-123", "Imei": "990000888", "ST_KEY_1": "some-value"}'
    print(f"Original Message: {message}")
    
    # Encrypt
    box = SealedBox(pk)
    encrypted = box.encrypt(message)
    encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
    
    print(f"Encrypted (B64): {encrypted_b64[:20]}...")
    
    # Decrypt using the utility
    try:
        decrypted = decrypt_ciphertext_b64(encrypted_b64, sk_b64)
        print(f"Decrypted: {decrypted}")
        assert decrypted == message.decode('utf-8')
        print("SUCCESS: Decryption logic verified.")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    test_decryption()
