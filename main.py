import sys
from interface import console, web

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'console'
    
    if mode == 'web':
        web()
    else:
        console()
