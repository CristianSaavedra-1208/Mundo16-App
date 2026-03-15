import pandas as pd
from app import *
from db import *
from core import motor_financiero_v20

df_c = pd.DataFrame(cargar_contratos())
errores = 0
for _, c in df_c.iterrows():
    try:
        motor_financiero_v20(c)
    except Exception as e:
        print(f"Error fatal en {c['Codigo_Interno']}: {e}")
        errores += 1

print(f"Total contratos analizados: {len(df_c)}")
print(f"Total errores fatales en motor: {errores}")
