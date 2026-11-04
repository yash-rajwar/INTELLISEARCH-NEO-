"""Run before first showcase launch. No credentials, network modifications or indexing."""
import importlib
import os
import socket
import sys
from pathlib import Path
from config import PROJECT,ROOT,BOOK_FILES,PORT

def main():
    print('IntelliSearch V3 — safe preflight (read-only)')
    print('Python:',sys.version.split()[0]);print('Project:',PROJECT)
    failures=[]
    if sys.version_info<(3,10):failures.append('Python 3.10 or newer required')
    for name in ('flask','requests','pypdf','docx','fitz'):
        try:
            m=importlib.import_module(name)
            print('  '+name+': installed')
        except ImportError:failures.append('Missing Python package '+name)
    folders=[ROOT/'templates', ROOT/'static',PROJECT/'clean_books']
    for f in folders:
        print(('OK' if f.is_dir() else 'MISSING')+' folder: '+str(f))
        if not f.is_dir():failures.append('Missing '+str(f))
    for book,filename in BOOK_FILES.items():
        p=PROJECT/'clean_books'/filename
        if not p.is_file():
            print('  NOTE: original book source missing:',filename)
    for port,desc in [(9200,'Elasticsearch'),(PORT,'showcase')]:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.settimeout(2)
            taken=s.connect_ex(('127.0.0.1',port))==0
        if port==9200 and not taken:failures.append('Elasticsearch port 9200 is not listening')
        if port==PORT and taken:failures.append('Port 5003 is already in use; stop that service first')
        print(desc,port,':','listening' if taken else 'not listening')
    try:
        from ocr import available
        status,message=available()
        print('  Optional OCR:', 'ready' if status else message)
    except Exception as exc:print('  Optional OCR check unavailable:',exc)
    from llm import enabled
    print('  Optional local AI:', 'configured' if enabled() else 'not configured; evidence-only mode available')
    if failures:
        print('\nPRE-FLIGHT FAILED:')
        for i in failures:print(' -',i)
        raise SystemExit(1)
    print('\nPRE-FLIGHT PASSED. Next: .\\.intellisearch_v2_env\\Scripts\\python.exe .\\intellisearch_showcase_v3\\app.py')
if __name__=='__main__':main()
