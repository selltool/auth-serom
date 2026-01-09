from nacl.public import PrivateKey, SealedBox
import base64
import os

def decrypt_ciphertext_b64(ciphertext_b64: str, private_key_b64: str) -> str:
    """
    Decrypts a base64 encoded ciphertext using the provided base64 encoded private key.
    """
    try:
        sk = PrivateKey(base64.b64decode(private_key_b64))
        box = SealedBox(sk)

        ciphertext = base64.b64decode(ciphertext_b64)
        plaintext_bytes = box.decrypt(ciphertext)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
