
import sys
import os
import inspect

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange

print("Methods in LighterExchange:")
for name, obj in inspect.getmembers(LighterExchange):
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        print(name)
