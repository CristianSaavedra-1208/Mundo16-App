import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from app import *
from db import *
from core import *

m = 'Diciembre'
a = 2024
f_t = pd.to_datetime(date(a, MESES_LISTA.index(m)+1, 1)) + relativedelta(day=31)

df_c = pd.DataFrame(cargar_contratos())
print('Total contratos cargados:', len(df_c))

res = []
for _, c in df_c.iterrows():
    if f_t < pd.to_datetime(c['Inicio']).replace(day=1): continue
    
    try:
        tab, vp, rou = motor_financiero_v20(c)
        past = tab[tab['Fecha'] <= f_t]
        if not past.empty:
            res.append({'Empresa': c['Empresa'], 'Nombre': c['Nombre']})
    except Exception as e:
        print(f"Error procesando {c['Codigo_Interno']}: {e}")

df_res = pd.DataFrame(res)
print('Contratos post filtros:', len(df_res))
if not df_res.empty:
    df_grp = df_res.groupby('Empresa').size()
    print('Cantidad por Empresa:\n', df_grp)
