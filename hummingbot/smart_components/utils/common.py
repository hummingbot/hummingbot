import hashlib
import random
import time

import base58


def generate_unique_id():
    timestamp = time.time()
    unique_component = random.randint(0, 99999)
    raw_id = f"{timestamp}-{unique_component}"
    hashed_id = hashlib.sha256(raw_id.encode()).digest()
    return base58.b58encode(hashed_id).decode()
