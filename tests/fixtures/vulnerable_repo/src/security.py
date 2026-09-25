"""Intentionally vulnerable security fixture for test coverage."""

import hashlib
import os
import pickle
import subprocess


# 1. Hard-coded credentials
api_key = "FAKE_TEST_API_KEY_12345678901234567890"
password = "FAKE_TEST_PASSWORD_SECRET_123"


# 2. Dynamic execution
def run_dynamic(user_code: str):
    eval(user_code)
    exec(user_code)


# 3. Unsafe subprocess with shell=True
def run_shell(command: str):
    subprocess.run(command, shell=True)


# 4. Unsafe deserialization
def load_data(raw_bytes: bytes):
    return pickle.loads(raw_bytes)


# 5. SQL injection risk
def get_user_sql(cursor, user_id: str):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)


# 6. Command injection risk
def execute_system(target: str):
    os.system(f"ping -c 1 {target}")


# 7. Path traversal risk
def read_user_file(filename: str):
    with open(f"/var/data/{filename}", "r") as f:
        return f.read()


# 8. Weak crypto
def hash_password(pwd: str):
    return hashlib.md5(pwd.encode("utf-8")).hexdigest()


def hash_token(tok: str):
    return hashlib.sha1(tok.encode("utf-8")).hexdigest()



# 9. Disabled TLS verification
class DummyRequests:
    @staticmethod
    def get(url, verify=True):
        return None

requests = DummyRequests()

def fetch_data(endpoint: str):
    return requests.get(endpoint, verify=False)


# 10. Debug settings
class App:
    def run(self, debug=False):
        pass

app = App()

def start_server():
    app.run(debug=True)
