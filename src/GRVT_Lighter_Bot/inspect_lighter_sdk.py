
import sys
import os
import inspect

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import lighter
    from lighter.api import info_api
    
    print("Classes in lighter module:")
    for name, obj in inspect.getmembers(lighter):
        if inspect.isclass(obj):
            print(name)
            
    print("\nMethods in InfoApi:")
    for name, obj in inspect.getmembers(info_api.InfoApi):
        if not name.startswith("_"):
            print(name)

except ImportError as e:
    print(f"Import Error: {e}")
