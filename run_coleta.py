#!/usr/bin/env python
"""
Wrapper para rodar a coleta sem problemas de bash/git
"""
import subprocess
import sys
import os

os.chdir(r"c:\Users\hvcam\Meu Drive\Pessoal\Mestrado\Dissertação\agroia-rmc")

# Rodar etapa3_producao.py com --resume
result = subprocess.run([sys.executable, "etapa3_producao.py", "--resume"])
sys.exit(result.returncode)
