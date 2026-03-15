import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from app import MESES_LISTA, to_excel
from db import cargar_contratos
from core import motor_financiero_v20, obtener_tc_cache

m = 'Diciembre'
a = 2024
f_t = pd.to_datetime(date(a, MESES_LISTA.index(m)+1, 1)) + relativedelta(day=31)

df_c = pd.DataFrame(cargar_contratos())
empresas = ["Todas"] + df_c['Empresa'].unique().tolist()
emp_sel = "Pacifico"

res = []
for _, c in df_c.iterrows():
    if emp_sel != "Todas" and c['Empresa'] != emp_sel: continue
    if f_t < pd.to_datetime(c['Inicio']).replace(day=1): continue
    
    if c.get('Fecha_Baja') and c['Estado'] == 'Baja':
        f_baja = pd.to_datetime(c['Fecha_Baja'])
        if f_baja <= f_t: continue
        
    tab, _, _ = motor_financiero_v20(c)
    futuros = tab[tab['Fecha'] > f_t]
    if futuros.empty: continue
    
    tc = obtener_tc_cache(c['Moneda'], f_t)
    
    for _, f in futuros.iterrows():
        f_pago = f['Fecha']
        pago_clp = f['Pago_Orig'] * tc
        dias = (f_pago - f_t).days
        
        if dias <= 90:
            b_id = '90 días'
            b_orden = 1
        elif dias <= 365:
            b_id = '90 días a 1 año'
            b_orden = 2
        elif dias <= 1095:  # 3 años
            b_id = '2 a 3 años'
            b_orden = 3
        elif dias <= 2555:  # 7 años
            b_id = '4 a 7 años'
            b_orden = 4
        else:
            b_id = 'Más de 7 años'
            b_orden = 5
            
        res.append({
            'Clase_Activo': c['Clase_Activo'],
            'Bucket': b_id,
            'Orden': b_orden,
            'Monto': pago_clp
        })
        
if not res:
    print("No hay flujos futuros a rendir (Pasivos no descontados = 0).")
    exit()

df_res = pd.DataFrame(res)
piv = df_res.groupby(['Clase_Activo', 'Bucket', 'Orden'])['Monto'].sum().unstack(['Bucket', 'Orden']).fillna(0)
piv.columns = [col[0] for col in piv.columns.to_flat_index()]

piv['Total Corriente'] = piv.get('90 días', 0) + piv.get('90 días a 1 año', 0)
piv['Total No Corriente'] = piv.get('2 a 3 años', 0) + piv.get('4 a 7 años', 0) + piv.get('Más de 7 años', 0)

todas_cols = ['90 días', '90 días a 1 año', 'Total Corriente', '2 a 3 años', '4 a 7 años', 'Más de 7 años', 'Total No Corriente']
cols_finales = [c for c in todas_cols if c in piv.columns]
piv = piv[cols_finales]

piv = piv / 1000
piv.loc['Total'] = piv.sum()

print(piv.head(10).to_string())
