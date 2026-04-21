"""
Configuración de pytest para el backend.

Añade el directorio backend/ al sys.path para que los imports absolutos
(domain.*, infrastructure.*, etc.) funcionen cuando pytest se ejecuta
desde la raíz del proyecto o desde backend/.
"""

import os
import sys

# Garantiza que 'backend/' sea la raíz de importación, igual que cuando
# uvicorn arranca con `uvicorn main:app` desde ese directorio.
sys.path.insert(0, os.path.dirname(__file__))
