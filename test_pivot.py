import pandas as pd

res = [
    {'Clase_Activo': 'Inmuebles', 'Bucket': '90 días', 'Orden': 1, 'Monto': 3407259000},
    {'Clase_Activo': 'Inmuebles', 'Bucket': '90 días a 1 año', 'Orden': 2, 'Monto': 9169244000},
    {'Clase_Activo': 'Inmuebles', 'Bucket': '2 a 3 años', 'Orden': 3, 'Monto': 9737165000},
    {'Clase_Activo': 'Vehículos', 'Bucket': '4 a 7 años', 'Orden': 4, 'Monto': 10237965000}
]

df_res = pd.DataFrame(res)
piv = df_res.groupby(['Clase_Activo', 'Bucket', 'Orden'])['Monto'].sum().unstack(['Bucket', 'Orden']).fillna(0)
print(piv.columns)

piv.columns = [col[0] for col in piv.columns.to_flat_index()]

# Calcular subtotales
piv['Total Corriente'] = piv.get('90 días', 0) + piv.get('90 días a 1 año', 0)
piv['Total No Corriente'] = piv.get('2 a 3 años', 0) + piv.get('4 a 7 años', 0) + piv.get('Más de 7 años', 0)

cols_ordenadas = ['90 días', '90 días a 1 año', 'Total Corriente', '2 a 3 años', '4 a 7 años', 'Más de 7 años', 'Total No Corriente']
cols_finales = [c for c in cols_ordenadas if c in piv.columns]
piv = piv[cols_finales]

piv = piv / 1000
piv.loc['Total'] = piv.sum()

print(piv)
