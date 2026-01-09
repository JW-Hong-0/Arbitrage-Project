import sys
import os
import inspect

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import lighter
    from lighter.signer_client import SignerClient
    
    print("\nMethods in SignerClient:")
    for name, obj in inspect.getmembers(SignerClient):
        if not name.startswith("_"):
            try:
                sig = inspect.signature(obj)
                print(f"{name}{sig}")
            except ValueError:
                print(f"{name} (no signature available)")

except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Error: {e}")
