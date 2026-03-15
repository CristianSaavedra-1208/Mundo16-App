import pandas as pd
from dateutil.relativedelta import relativedelta
import sys

# Crear un mock de streamlit para no requerir UI
with open("mock_streamlit.py", "w") as f:
    f.write("def cache_data(func): return func\n")
    f.write("def stop(): sys.exit(1)\n")
    f.write("def error(msg): print('ERROR:', msg)\n")

# Mock dependencias para importar core.py
import mock_streamlit as st 
sys.modules['streamlit'] = st

# Importar motor
import core
from core import motor_financiero_v20

# Mock DB loader
def mock_cargar_remediciones(cod):
    if cod == "TEST_REM_01":
        return [{
            "Codigo_Interno": "TEST_REM_01",
            "Fecha_Remedicion": "2024-06-01",
            "Canon": 120000,
            "Tasa": 0.08,
            "Tasa_Mensual": pow(1.08, 1/12)-1,
            "Fin": "2025-12-31",
            "Plazo": 19,
            "Ajuste_ROU": 50000.0
        }]
    return []

core.cargar_remediciones = mock_cargar_remediciones

def auditar_contrato(nombre, c, expected_vp_range=None):
    print(f"\\n{'='*50}\\nAuditando Escenario: {nombre}")
    df, vp, rou = motor_financiero_v20(c)
    
    pasivo_fin = df.iloc[-1]['S_Fin_Orig'] if not df.empty else 0
    pasivo_ini = df.iloc[0]['S_Ini_Orig'] if not df.empty else 0
    amortizacion_total = df['Dep_Orig'].sum() if not df.empty else 0
    
    # 1. Validación de Cuadre de Pasivo
    pass_1 = abs(pasivo_fin) < 1.0
    print(f"[1] Cuadre Pasivo a Cero: {'PASS' if pass_1 else 'FAIL'} (Saldo Final: {pasivo_fin})")
    
    # 2. Validación de Amortización ROU
    # En casos sin remedición, el ROU se debe depreciar completo
    if c['Codigo_Interno'] != "TEST_REM_01" and not c.get('Fecha_Baja'):
        pass_2 = abs(amortizacion_total - rou) < 1.0
        print(f"[2] Depreciación Completa ROU: {'PASS' if pass_2 else 'FAIL'} (Dep: {amortizacion_total}, ROU: {rou})")

    # 3. Validación de Costos Directos e Incentivos impactando el ROU Inicial
    if c.get('Costos_Directos', 0) > 0 or c.get('Incentivos', 0) > 0:
        base_rou = c.get('Costos_Directos', 0) + c.get('Pagos_Anticipados', 0) + c.get('Costos_Desmantelamiento', 0) - c.get('Incentivos', 0)
        pass_3 = abs(rou - (vp + base_rou)) < 1.0
        print(f"[3] Impacto Componentes ROU: {'PASS' if pass_3 else 'FAIL'} (Dif VP-ROU: {rou - vp})")
        
    if expected_vp_range:
        pass_vp = expected_vp_range[0] <= vp <= expected_vp_range[1]
        print(f"[4] Tasa VP Esperada: {'PASS' if pass_vp else 'FAIL'} (VP Obtenido: {vp})")
        
    return df

# CASO 1: Contrato Básico Pagos Vencidos (Típico)
c1 = {
    'Codigo_Interno': 'TEST_01', 'Inicio': '2024-01-01', 'Fin': '2024-12-31',
    'Canon': 100000, 'Tasa': 0.05, 'Tasa_Mensual': pow(1.05, 1/12)-1,
    'Plazo': 12, 'Tipo_Pago': 'Vencido', 'Estado': 'Activo'
}
df1 = auditar_contrato("Básico Vencido, 12 Meses, 100k CLP", c1)

# CASO 2: Contrato Pagos Anticipados con Incentivos y Costos
c2 = {
    'Codigo_Interno': 'TEST_02', 'Inicio': '2024-01-01', 'Fin': '2026-12-31',
    'Canon': 500000, 'Tasa': 0.12, 'Tasa_Mensual': pow(1.12, 1/12)-1,
    'Plazo': 36, 'Tipo_Pago': 'Anticipado', 'Estado': 'Activo',
    'Costos_Directos': 150000, 'Incentivos': 50000, 'Costos_Desmantelamiento': 100000
}
df2 = auditar_contrato("Pagos Anticipados, 36 Meses, Costos Extra", c2)

# CASO 3: Baja Anticipada al mes 6 (de un contrato de 12)
c3 = {
    'Codigo_Interno': 'TEST_03', 'Inicio': '2024-01-01', 'Fin': '2024-12-31',
    'Canon': 100000, 'Tasa': 0.05, 'Tasa_Mensual': pow(1.05, 1/12)-1,
    'Plazo': 12, 'Tipo_Pago': 'Vencido', 'Estado': 'Baja', 'Fecha_Baja': '2024-06-15' # Baja en Junio
}
df3 = auditar_contrato("Baja Anticipada Mes 6", c3)
if len(df3) == 6:
    print("[5] Truncamiento Fecha_Baja: PASS (Generó 6 registros de 12)")
else:
    print(f"[5] Truncamiento Fecha_Baja: FAIL (Generó {len(df3)} registros)")

# CASO 4: Contrato con Remedición a mitad de camino (ver mock de db)
c4 = {
    'Codigo_Interno': 'TEST_REM_01', 'Inicio': '2024-01-01', 'Fin': '2025-12-31',
    'Canon': 100000, 'Tasa': 0.05, 'Tasa_Mensual': pow(1.05, 1/12)-1,
    'Plazo': 24, 'Tipo_Pago': 'Vencido', 'Estado': 'Activo'
}
df4 = auditar_contrato("Contrato con Tramo de Remedición (Aumenta Canon en mes 6)", c4)
if len(df4) == 24:
    print("[6] Cosedura Histórica de Remedición: PASS (Recorrió los 24 meses ensamblados)")
else:
    print(f"[6] Cosedura Histórica de Remedición: FAIL (Generó {len(df4)} vs 24 meses)")
