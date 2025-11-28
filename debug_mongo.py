import os
import certifi
import ssl
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv("db/.env")

def test_connection(name, **kwargs):
    print(f"\n--- Testing Connection: {name} ---")
    print(f"Params: {kwargs}")
    
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("MONGO_URI not found in environment.")
        return

    try:
        client = MongoClient(uri, **kwargs)
        # Force a connection attempt
        client.admin.command('ping')
        print("✅ Connection Successful!")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        # Print detailed SSL error if available
        if hasattr(e, 'reason'):
            print(f"Reason: {e.reason}")

# Test 1: Default (relying on system certs)
test_connection("Default")

# Test 2: With certifi (tlsCAFile)
test_connection("With certifi", tlsCAFile=certifi.where())

# Test 3: With certifi + tls=True
test_connection("Certifi + tls=True", tlsCAFile=certifi.where(), tls=True)

# Test 4: With certifi + tls=True + tlsAllowInvalidCertificates=True
test_connection("Certifi + tls + AllowInvalid", tlsCAFile=certifi.where(), tls=True, tlsAllowInvalidCertificates=True)

# Test 5: Explicit SSL Context
try:
    ctx = ssl.create_default_context(cafile=certifi.where())
    test_connection("Explicit SSL Context", tls=True, ssl_context=ctx)
except Exception as e:
    print(f"Failed to create SSL context: {e}")
