import pandas as pd
import streamlit as st
import io

@st.cache_data
def obtener_df_monedas_cache():
    from db import cargar_monedas
    return cargar_monedas()

def obtener_tc_cache(moneda, fecha):
    if moneda == "CLP": return 1.0
    df = obtener_df_monedas_cache()
    if df.empty: return 0.0
    try:
        f_s = pd.to_datetime(fecha).strftime('%Y-%m-%d')
        res = df[(df['moneda'] == moneda) & (df['fecha'] <= f_s)]
        return res.iloc[0]['valor'] if not res.empty else 0.0
    except: return 0.0

def __calc_vp(can, p, t_m, tipo):
    if p <= 0: return 0.0
    if t_m > 0:
        if tipo == "Anticipado": return can * ((1 - (1 + t_m)**-p) / t_m) * (1 + t_m)
        else: return can * ((1 - (1 + t_m)**-p) / t_m)
    else: return can * p

import numpy as np

@st.cache_data
def motor_financiero_v20(c):
    from db import cargar_remediciones
    rems = cargar_remediciones(c['Codigo_Interno'])
    
    # Hito 1: Parámetros del contrato Original (antes de cualquier remedición)
    f_i = pd.to_datetime(c['Inicio'])
    tipo = c.get('Tipo_Pago', 'Vencido')
    
    # Calcular ROU Inicial Original
    cd = float(c.get('Costos_Directos', 0.0))
    pa = float(c.get('Pagos_Anticipados', 0.0))
    cdesm = float(c.get('Costos_Desmantelamiento', 0.0))
    inc = float(c.get('Incentivos', 0.0))
    ajuste_orig = float(c.get('Ajuste_ROU', 0.0))
    
    vp_orig = __calc_vp(float(c['Canon']), int(c['Plazo']), float(c['Tasa_Mensual']), tipo)
    rou_orig = vp_orig + cd + pa + cdesm - inc + ajuste_orig
    
    tramos = []
    tramos.append({
        'Fecha_Inicio': f_i,
        'Canon': float(c['Canon']),
        'Tasa_Mensual': float(c['Tasa_Mensual']),
        'Plazo': int(c['Plazo']),
        'Ajuste_ROU': ajuste_orig,
        'Es_Remedicion': False
    })
    
    for r in rems:
        tramos.append({
            'Fecha_Inicio': pd.to_datetime(r['Fecha_Remedicion']),
            'Canon': float(r['Canon']),
            'Tasa_Mensual': float(r['Tasa_Mensual']),
            'Plazo': int(r['Plazo']),
            'Ajuste_ROU': float(r['Ajuste_ROU']),
            'Es_Remedicion': True
        })
        
    f_baja_final = pd.to_datetime(c['Fecha_Baja']) if c.get('Fecha_Baja') and c['Estado'] == 'Baja' else None
    
    dfs = []
    mes_global = 1
    
    # Aunque iteramos los Tramos (suele ser 1, rara vez > 2), vectorizamos **dentro** del tramo.
    s_ini_pasivo = vp_orig
    s_ini_rou_net = rou_orig
    
    for idx, t in enumerate(tramos):
        f_tramo_ini = t['Fecha_Inicio']
        f_tramo_fin = tramos[idx+1]['Fecha_Inicio'] if idx+1 < len(tramos) else None
        
        if t['Es_Remedicion']:
            s_ini_pasivo = __calc_vp(t['Canon'], t['Plazo'], t['Tasa_Mensual'], tipo)
            s_ini_rou_net = s_ini_pasivo + t['Ajuste_ROU']
            
        plazo = t['Plazo']
        if plazo <= 0: continue
            
        dep_tramo = s_ini_rou_net / plazo
        
        # 1. Crear el array de índices (0 hasta plazo-1)
        periodos = np.arange(plazo)
        
        # 2. Generar Fechas Vectorizadas
        # date_range es sumamente eficiente en pandas
        fechas_reales = pd.date_range(start=f_tramo_ini, periods=plazo, freq=pd.DateOffset(months=1))
        
        # 3. Filtrar fechas según tramos de remedición o bajas
        mask = np.ones(plazo, dtype=bool)
        if f_tramo_fin:
            # Eliminar periodos >= Fecha del siguiente tramo
            mask = mask & ((fechas_reales.year < f_tramo_fin.year) | ((fechas_reales.year == f_tramo_fin.year) & (fechas_reales.month < f_tramo_fin.month)))
        if f_baja_final:
            # Eliminar periodos > Fecha de baja
            mask = mask & ((fechas_reales.year < f_baja_final.year) | ((fechas_reales.year == f_baja_final.year) & (fechas_reales.month <= f_baja_final.month)))
            
        valid_idx = np.where(mask)[0]
        if len(valid_idx) == 0: continue
        
        periodos_validos = periodos[valid_idx]
        fechas_validas = fechas_reales[valid_idx]
        n_meses = len(valid_idx)
        
        # 4. Matemáticas Financieras Vectorizadas
        # Si la tasa es 0, el PMT/IPMT/PPMT tira warning o error de división. Lo hacemos a mano:
        t_m = t['Tasa_Mensual']
        c_an = t['Canon']
        
        s_inis = np.zeros(n_meses)
        ints = np.zeros(n_meses)
        caps = np.zeros(n_meses)
        s_fins = np.zeros(n_meses)
        
        # Como es una tabla de amortización con cuota fija y saldo dinámico (que puede ser Vencido o Anticipado)
        # IPMT y PPMT estándar de numpy asumen siempre pagos vencidos y saldos iniciales fijos.
        # Para clavar el céntimo exacto de nuestro algoritmo iterativo (especialmente en Anticipado y cierre en último mes), 
        # usar formula cerrada de "Valor Presente en T".
        
        # P = Pago, i = tasa, n = plazo TOTAL del tramo
        # Saldo_en_T(t) = VP(restantes = n - t)
        
        t_array = periodos_validos # Ejemplo: [0, 1, 2, 3...]
        restantes = plazo - t_array # Ejemplo: [12, 11, 10, 9...]
        
        if t_m > 0:
            if tipo == "Anticipado":
                s_inis = c_an * ((1 - (1 + t_m)**(-restantes)) / t_m) * (1 + t_m)
                s_fins = c_an * ((1 - (1 + t_m)**(-(restantes - 1))) / t_m) * (1 + t_m)
                # El interés del mes anticipado se basa en (Saldo - Pago)
                ints = (s_inis - c_an) * t_m
                # Fix para la última cuota si fuera anticipado
                ints = np.maximum(0, ints) 
                
            else: # Vencido
                s_inis = c_an * ((1 - (1 + t_m)**(-restantes)) / t_m)
                s_fins = c_an * ((1 - (1 + t_m)**(-(restantes - 1))) / t_m)
                ints = s_inis * t_m
                
            caps = s_inis - s_fins
            # Fix última cuota (si se arrastra hasta el fin absoluto del tramo)
            es_ultima_cuota = (restantes == 1) & (idx == len(tramos) - 1)
            caps = np.where(es_ultima_cuota, s_inis, caps)
            ints = np.where(es_ultima_cuota, np.maximum(0, c_an - s_inis), ints)
            s_fins = np.where(es_ultima_cuota, 0.0, s_fins)
                
        else: # Tasa 0
            s_inis = c_an * restantes
            s_fins = c_an * (restantes - 1)
            ints = np.zeros(n_meses)
            caps = c_an
            s_fins = np.where((restantes == 1) & (idx == len(tramos) - 1), 0.0, s_fins)
            caps = np.where((restantes == 1) & (idx == len(tramos) - 1), s_inis, caps)
        
        # 5. Ensamblar DataFrame del tramo
        df_tramo = pd.DataFrame({
            'Mes': mes_global + np.arange(n_meses),
            'Fecha': fechas_validas,
            'S_Ini_Orig': np.round(s_inis, 4),
            'Int_Orig': np.round(ints, 4),
            'Pago_Orig': np.round(np.full(n_meses, c_an), 4),
            'Dep_Orig': np.round(np.full(n_meses, dep_tramo), 4),
            'S_Fin_Orig': np.round(s_fins, 4)
        })
        
        dfs.append(df_tramo)
        mes_global += n_meses
        
        # El saldo inicial (si hubiera otro tramo o se quisiera auditar de fuera) sería el fin de este tramo
        s_ini_pasivo = s_fins[-1] if n_meses > 0 else s_ini_pasivo
        
    if not dfs:
        return pd.DataFrame(), vp_orig, rou_orig
        
    final_df = pd.concat(dfs, ignore_index=True)
    return final_df, vp_orig, rou_orig

def generar_codigo_correlativo(empresa, lista_existente):
    prefix = empresa[:3].upper()
    count = len([c for c in lista_existente if c['Empresa'] == empresa]) + 1
    return f"CNT-{prefix}-{count:04d}"

def to_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as wr: df.to_excel(wr, index=False)
    return out.getvalue()