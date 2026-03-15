import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import io
from db import *
from core import *
st.set_page_config(page_title="Mundo 16", layout="wide")

# --- KILL SWITCH (Viernes 20 Marzo 2026) ---
FECHA_EXPIRACION = date(2026, 3, 20)
is_local = False
try:
    host = st.context.headers.get("Host", "")
    if "localhost" in host or "127.0.0.1" in host:
        is_local = True
except:
    pass

if not is_local and date.today() > FECHA_EXPIRACION:
    st.error("Acceso Denegado: La versión de prueba de Mundo 16 ha expirado. Contacte al administrador para soporte.")
    st.stop()

MESES_LISTA = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

if 'auth' not in st.session_state: st.session_state.auth = False
EMPRESAS_LISTA = obtener_parametros('EMPRESA')
CLASES_ACTIVO = obtener_parametros('CLASE_ACTIVO')

# --- FUNCIONES DE APOYO CONTABLE ---

def add_asiento(lista, emp, cod1, transaccion, n_cta, cuenta, debe, haber):
    # Forzar que solo exista Debe o Haber por línea. Si vienen ambos, se dividen.
    if abs(debe) > 0.01:
        lista.append({"Empresa": emp, "Cod1": cod1, "Transacción": transaccion, "N° Cuenta": str(n_cta), "Cuenta": str(cuenta), "Tipo": "Debe", "Debe": round(debe,0), "Haber": 0})
    if abs(haber) > 0.01:
        lista.append({"Empresa": emp, "Cod1": cod1, "Transacción": transaccion, "N° Cuenta": str(n_cta), "Cuenta": str(cuenta), "Tipo": "Haber", "Debe": 0, "Haber": round(haber,0)})

def obtener_motor_financiero(c):
    if 'motor_cache' not in st.session_state:
        st.session_state.motor_cache = {}
    
    cid = c['Codigo_Interno']
    hash_c = f"{c['Estado']}_{c['Canon']}_{c['Tasa']}_{c['Plazo']}_{c['Inicio']}_{c['Fin']}_{c.get('Fecha_Baja', '')}"
    
    if cid in st.session_state.motor_cache:
        cached_hash, tab, vp, rou = st.session_state.motor_cache[cid]
        if cached_hash == hash_c:
            return tab, vp, rou
            
    tab, vp, rou = motor_financiero_v20(c)
    st.session_state.motor_cache[cid] = (hash_c, tab, vp, rou)
    return tab, vp, rou

# --- MÓDULOS ---

def modulo_asientos():
    st.header("🧾 Registros Contables")
    c1, c2, c3 = st.columns(3)
    emp_sel = c1.selectbox("Empresa", ["Todas"] + EMPRESAS_LISTA, key="as_emp")
    m_nom = c2.selectbox("Mes", MESES_LISTA, key="as_m")
    a = c3.number_input("Año", value=date.today().year, key="as_a")
    
    if st.button("Generar Asientos", type="primary"):
        m_idx = MESES_LISTA.index(m_nom) + 1
        f_act = pd.to_datetime(date(a, m_idx, 1)) + relativedelta(day=31)
        f_ant = f_act - relativedelta(months=1, day=31)
        
        detalles = []
        lista_c = cargar_contratos()
        if emp_sel != "Todas": lista_c = [c for c in lista_c if c['Empresa'] == emp_sel]
        
        cta_map = {
            'ROU': (obtener_parametros('CUENTA_ROU_NUM')[0] if obtener_parametros('CUENTA_ROU_NUM') else '1401', obtener_parametros('CUENTA_ROU_NOM')[0] if obtener_parametros('CUENTA_ROU_NOM') else 'Activo ROU'),
            'Pasivo': (obtener_parametros('CUENTA_PASIVO_NUM')[0] if obtener_parametros('CUENTA_PASIVO_NUM') else '2101', obtener_parametros('CUENTA_PASIVO_NOM')[0] if obtener_parametros('CUENTA_PASIVO_NOM') else 'Pasivo IFRS 16'),
            'Ajuste': (obtener_parametros('CUENTA_BCO_AJUSTE_NUM')[0] if obtener_parametros('CUENTA_BCO_AJUSTE_NUM') else '1101', obtener_parametros('CUENTA_BCO_AJUSTE_NOM')[0] if obtener_parametros('CUENTA_BCO_AJUSTE_NOM') else 'Banco Ajustes'),
            'Amort': (obtener_parametros('CUENTA_GASTO_AMORT_NUM')[0] if obtener_parametros('CUENTA_GASTO_AMORT_NUM') else '4101', obtener_parametros('CUENTA_GASTO_AMORT_NOM')[0] if obtener_parametros('CUENTA_GASTO_AMORT_NOM') else 'Gasto Amort'),
            'AmortAcum': (obtener_parametros('CUENTA_AMORT_ACUM_NUM')[0] if obtener_parametros('CUENTA_AMORT_ACUM_NUM') else '1402', obtener_parametros('CUENTA_AMORT_ACUM_NOM')[0] if obtener_parametros('CUENTA_AMORT_ACUM_NOM') else 'Amort Acumulada'),
            'Interes': (obtener_parametros('CUENTA_GASTO_INT_NUM')[0] if obtener_parametros('CUENTA_GASTO_INT_NUM') else '4201', obtener_parametros('CUENTA_GASTO_INT_NOM')[0] if obtener_parametros('CUENTA_GASTO_INT_NOM') else 'Gasto Interés'),
            'Banco': (obtener_parametros('CUENTA_BANCO_PAGO_NUM')[0] if obtener_parametros('CUENTA_BANCO_PAGO_NUM') else '1102', obtener_parametros('CUENTA_BANCO_PAGO_NOM')[0] if obtener_parametros('CUENTA_BANCO_PAGO_NOM') else 'Banco Efectivo'),
            'Perdida': (obtener_parametros('CUENTA_PERDIDA_TC_NUM')[0] if obtener_parametros('CUENTA_PERDIDA_TC_NUM') else '4301', obtener_parametros('CUENTA_PERDIDA_TC_NOM')[0] if obtener_parametros('CUENTA_PERDIDA_TC_NOM') else 'Pérdida TC'),
            'Ganancia': (obtener_parametros('CUENTA_GANANCIA_TC_NUM')[0] if obtener_parametros('CUENTA_GANANCIA_TC_NUM') else '4302', obtener_parametros('CUENTA_GANANCIA_TC_NOM')[0] if obtener_parametros('CUENTA_GANANCIA_TC_NOM') else 'Ganancia TC')
        }
        
        for c in lista_c:
            f_ini = pd.to_datetime(c['Inicio'])
            if f_act < f_ini.replace(day=1): continue
            
            tab, vp, rou = obtener_motor_financiero(c)
            if tab.empty or 'Fecha' not in tab.columns: continue
            
            # 1. Asiento de Reconocimiento Inicial
            if f_ini.month == m_idx and f_ini.year == a:
                tc_ini = float(c['Valor_Moneda_Inicio']) if c['Valor_Moneda_Inicio'] > 0 else 1.0
                t_rec = "1. Reconocimiento Inicial"
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rec, *cta_map['ROU'], rou * tc_ini, 0)
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rec, *cta_map['Pasivo'], 0, vp * tc_ini)
                diff = (rou - vp) * tc_ini
                if diff > 0:
                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rec, *cta_map['Ajuste'], 0, diff)
                elif diff < 0:
                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rec, *cta_map['Ajuste'], abs(diff), 0)
    
            # Asientos Mensuales (Amortización, Intereses, Pagos y Reajuste)
            fila = tab[(tab['Fecha'].dt.month == m_idx) & (tab['Fecha'].dt.year == a)]
            if not fila.empty:
                it = fila.iloc[0]
                tc_act = obtener_tc_cache(c['Moneda'], f_act)
                
                # Ajuste crucial: Si es la primera cuota (Mes 1), la UF anterior es la de inicio del contrato
                if it['Mes'] == 1:
                    tc_ant = float(c['Valor_Moneda_Inicio']) if float(c['Valor_Moneda_Inicio']) > 0 else 1.0
                else:
                    tc_ant = obtener_tc_cache(c['Moneda'], f_ant)
                    
                ratio_act = tc_act
                ratio_ant = tc_ant
                
                t_amo = "2. Amortización"
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_amo, *cta_map['Amort'], it['Dep_Orig'] * ratio_act, 0)
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_amo, *cta_map['AmortAcum'], 0, it['Dep_Orig'] * ratio_act)
                
                t_pag = "3. Pago de Arriendo ROU"
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_pag, *cta_map['Pasivo'], it['Pago_Orig'] * ratio_act, 0)
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_pag, *cta_map['Banco'], 0, it['Pago_Orig'] * ratio_act)
                
                t_int = "4. Intereses"
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_int, *cta_map['Interes'], it['Int_Orig'] * ratio_act, 0)
                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_int, *cta_map['Pasivo'], 0, it['Int_Orig'] * ratio_act)
                
                t_tc = "5. Diferencia de Cambio"
                reajuste = (it['S_Fin_Orig'] * ratio_act) - (it['S_Fin_Orig'] * ratio_ant)
                if abs(reajuste) > 0.1:
                    if reajuste > 0: 
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_tc, *cta_map['Perdida'], reajuste, 0)
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_tc, *cta_map['Pasivo'], 0, reajuste)
                    else:
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_tc, *cta_map['Pasivo'], abs(reajuste), 0)
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_tc, *cta_map['Ganancia'], 0, abs(reajuste))
    
            # Asiento de Baja Definitiva o Remedición
            if c.get('Fecha_Baja') and c['Estado'] in ['Baja', 'Remedido']:
                f_baja = pd.to_datetime(c['Fecha_Baja'])
                if f_baja.month == m_idx and f_baja.year == a:
                    # Calcular saldos al momento del cese/remedición
                    pasado = tab[tab['Fecha'] <= f_baja]
                    if not pasado.empty:
                        tc_baja = obtener_tc_cache(c['Moneda'], f_baja)
                        s_fin_pasivo = pasado.iloc[-1]['S_Fin_Orig'] * tc_baja
                        amort_acum = pasado['Dep_Orig'].sum() * tc_baja
                        s_fin_rou = (rou * tc_baja) - amort_acum
                        
                        if s_fin_pasivo > 0.01 or s_fin_rou > 0.01:
                            if c['Estado'] == 'Remedido':
                                t_baja = "7. Cierre por Remedición"
                                # Reversar Pasivo
                                if s_fin_pasivo > 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Pasivo'], s_fin_pasivo, 0)
                                
                                # Reversar ROU y Amort
                                r_neto = (rou * tc_baja)
                                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['ROU'], 0, r_neto)
                                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['AmortAcum'], amort_acum, 0)
                                
                                # Diferencia a Ajuste (SIN P&L)
                                dif_baja = s_fin_pasivo - s_fin_rou
                                if dif_baja > 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Ajuste'], 0, dif_baja)
                                elif dif_baja < 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Ajuste'], abs(dif_baja), 0)
                            else:
                                t_baja = "6. Baja Definitiva de Contrato"
                                if s_fin_pasivo > 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Pasivo'], s_fin_pasivo, 0)
                                r_neto = (rou * tc_baja)
                                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['ROU'], 0, r_neto)
                                add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['AmortAcum'], amort_acum, 0)
                                dif_baja = s_fin_pasivo - s_fin_rou
                                if dif_baja > 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Ganancia'], 0, dif_baja)
                                elif dif_baja < 0:
                                    add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_baja, *cta_map['Perdida'], abs(dif_baja), 0)
    
            # Asiento de Ajuste por Remedición
            from db import cargar_remediciones
            rems = cargar_remediciones(c['Codigo_Interno'])
            for r in rems:
                f_r = pd.to_datetime(r['Fecha_Remedicion'])
                if f_r.month == m_idx and f_r.year == a:
                    t_rem = "7. Ajuste por Remedición"
                    aj = r['Ajuste_ROU']
                    if aj > 0:
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rem, *cta_map['ROU'], aj, 0)
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rem, *cta_map['Pasivo'], 0, aj)
                    elif aj < 0:
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rem, *cta_map['Pasivo'], abs(aj), 0)
                        add_asiento(detalles, c['Empresa'], c['Codigo_Interno'], t_rem, *cta_map['ROU'], 0, abs(aj))

        st.session_state.asientos_data = detalles
        st.session_state.asientos_params = {'m': m_nom, 'a': a}

    if 'asientos_data' in st.session_state:
        detalles = st.session_state.asientos_data
        m_saved = st.session_state.asientos_params['m']
        a_saved = st.session_state.asientos_params['a']
        
        t1, t2 = st.tabs(["Resumen Mensual Contable", "Detalle por Contrato"])
        
        with t2:
            if detalles:
                df_asientos = pd.DataFrame(detalles)
                df_asientos.rename(columns={'Cod1': 'ID_Contrato'}, inplace=True)
                # Agregar Fila Total al Detalle
                df_asientos.loc['Total'] = df_asientos.sum(numeric_only=True)
                df_asientos.at['Total', 'Empresa'] = 'TOTALES'
                df_asientos.at['Total', 'Cuenta'] = 'CUADRATURA'
                
                st.dataframe(df_asientos.style.format(precision=0, thousands="."))
                st.download_button("Exportar Detalle de Asientos (Excel)", to_excel(df_asientos), f"Detalle_Asientos_{m_saved}_{a_saved}.xlsx")
            else:
                st.info("No hay movimientos granulares para esta selección.")
                
        with t1:
            if detalles:
                df_asientos = pd.DataFrame(detalles)
                df_resumen = df_asientos.groupby(['Empresa', 'Transacción', 'N° Cuenta', 'Cuenta', 'Tipo']).sum(numeric_only=True).reset_index()
                # Fila de cuadratura
                df_resumen.loc['Total'] = df_resumen.sum(numeric_only=True)
                df_resumen.at['Total', 'Empresa'] = 'TOTALES'
                df_resumen.at['Total', 'Transacción'] = ''
                df_resumen.at['Total', 'N° Cuenta'] = ''
                df_resumen.at['Total', 'Cuenta'] = 'CUADRATURA PERFECTA'
                df_resumen.at['Total', 'Tipo'] = ''
                st.dataframe(df_resumen.style.format(precision=0, thousands="."))
                st.download_button("Exportar Asientos Resumidos (Excel)", to_excel(df_resumen), f"Resumen_Asientos_{m_saved}_{a_saved}.xlsx")
            else:
                st.info("No hay movimientos para esta selección.")

def modulo_notas():
    st.header("📋 Movimiento de saldos (Nota de Pasivos y Activos)")
    c1, c2, c3 = st.columns(3)
    emp_sel = c1.selectbox("Empresa", ["Todas"] + EMPRESAS_LISTA, key="nt_emp")
    m_nom = c2.selectbox("Mes Nota", MESES_LISTA, key="nt_m")
    a = c3.number_input("Año Nota", value=date.today().year, key="nt_a")
    
    if st.button("Generar Movimiento de saldos", type="primary"):
        m_idx = MESES_LISTA.index(m_nom) + 1
        f_act = pd.to_datetime(date(a, m_idx, 1)) + relativedelta(day=31)
        f_ant = pd.to_datetime(date(a - 1, 12, 31))
        
        roll_pasivo = []
        roll_activo = []
        
        lista_c = cargar_contratos()
        if emp_sel != "Todas": lista_c = [c for c in lista_c if c['Empresa'] == emp_sel]
            
        for c in lista_c:
            f_ini_c = pd.to_datetime(c['Inicio'])
            if f_act < f_ini_c.replace(day=1): continue
            
            tab, vp, rou = obtener_motor_financiero(c)
            if tab.empty or 'Fecha' not in tab.columns: continue
            tc_act = obtener_tc_cache(c['Moneda'], f_act)
            tc_ant = obtener_tc_cache(c['Moneda'], f_ant)
            r_act_pasivo = tc_act 
            r_ant_pasivo = tc_ant 
            
            tc_ini = float(c['Valor_Moneda_Inicio']) if c.get('Valor_Moneda_Inicio') and float(c['Valor_Moneda_Inicio']) > 0 else 1.0
            r_act_rou = tc_ini
            r_ant_rou = tc_ini
            
            f_ini_c = pd.to_datetime(c['Inicio'])
            fue_adicionado = (f_ini_c.year == a)
            
            # Saldo Inicial (Cierre del año anterior YTD)
            past_ant = tab[tab['Fecha'] <= f_ant]
            if fue_adicionado:
                s_ini = 0
                s_ini_rou = 0
                s_ini_orig = 0
                s_ini_rou_orig = 0
            else:
                s_ini_orig = past_ant.iloc[-1]['S_Fin_Orig'] if not past_ant.empty else 0
                s_ini = s_ini_orig * r_ant_pasivo
                
                s_ini_rou_orig = rou - (past_ant['Dep_Orig'].sum() if not past_ant.empty else 0)
                s_ini_rou = s_ini_rou_orig * r_ant_rou
            
            # Reconocimiento Inicial (Adiciones YTD)
            if fue_adicionado:
                adic_pasivo = vp * tc_ini
                adic_rou = rou * tc_ini
            else:
                adic_pasivo = 0
                adic_rou = 0
                
            # Movimientos del año (YTD) hasta el mes seleccionado
            curr = tab[(tab['Fecha'].dt.year == a) & (tab['Fecha'].dt.month <= m_idx)]
            interes = curr['Int_Orig'].sum() * r_act_pasivo if not curr.empty else 0
            pagos = curr['Pago_Orig'].sum() * r_act_pasivo if not curr.empty else 0
            amortizacion = curr['Dep_Orig'].sum() * r_act_rou if not curr.empty else 0
            
            # 4. Modificadores (Bajas, Remediciones) 
            from db import cargar_remediciones
            rems = cargar_remediciones(c['Codigo_Interno'])
            bajas_p, bajas_a = 0, 0
            rem_p, rem_a = 0, 0
            
            # Las remediciones sumarán el valor del ajuste ROU inyectado en ese periodo
            for r in rems:
                f_r = pd.to_datetime(r['Fecha_Remedicion'])
                # Filtramos que haya ocurrido en el YTD hasta el mes evaluado
                if f_r.year == a and f_r.month <= m_idx:
                    rem_a += r['Ajuste_ROU']
                    
            # 5. Fijación Excéntrica del Saldo Final (Fotografía Real)
            curr_fin = tab[tab['Fecha'] <= f_act]
            if not curr_fin.empty:
                s_fin_orig_real = curr_fin.iloc[-1]['S_Fin_Orig']
                dep_acum_real = curr_fin['Dep_Orig'].sum()
            else:
                s_fin_orig_real = vp
                dep_acum_real = 0
                
            s_fin_real = s_fin_orig_real * r_act_pasivo
            s_fin_rou_real = (rou * r_act_rou) + rem_a - (dep_acum_real * r_act_rou)

            # Validar Bajas Definitivas en el YTD
            es_baja = False
            if c.get('Fecha_Baja') and c['Estado'] == 'Baja':
                f_baja = pd.to_datetime(c['Fecha_Baja'])
                if f_baja.year == a and f_baja.month <= m_idx:
                    es_baja = True
                    bajas_p = -s_fin_real
                    bajas_a = -s_fin_rou_real
                    s_fin_real = 0
                    s_fin_rou_real = 0
                    
            # 6. Recalcular la Diferencia de Cambio como "Plug" (Cuadratura Perfecta)
            # Puente Teórico = S_Ini + Adiciones + Interes - Pagos + Rem_P + Dif_Cambio = S_Fin
            # Despejando -> Dif_Cambio = S_Fin - S_Ini - Adiciones - Interes + Pagos - Rem_P - Bajas
            reajuste = s_fin_real - s_ini - adic_pasivo - interes + pagos - rem_p - bajas_p
            reajuste_rou = s_fin_rou_real - s_ini_rou - adic_rou - rem_a + amortizacion - bajas_a
                    
            roll_pasivo.append({"ID_Contrato": c['Codigo_Interno'], "Empresa": c['Empresa'], "Clase_Activo": c['Clase_Activo'], "Contrato": c['Nombre'], "S.Inicial": s_ini, "Adiciones": adic_pasivo, "Remediciones": rem_p, "Interés": interes, "Dif. Cambio": reajuste, "Pagos": pagos, "Bajas": bajas_p, "S.Final": s_fin_real})
            roll_activo.append({"ID_Contrato": c['Codigo_Interno'], "Empresa": c['Empresa'], "Clase_Activo": c['Clase_Activo'], "Contrato": c['Nombre'], "S.Inicial": s_ini_rou, "Adiciones": adic_rou, "Remediciones": rem_a, "Amortización": amortizacion, "Dif. Cambio": reajuste_rou, "Bajas": bajas_a, "S.Final": s_fin_rou_real})
        
        st.session_state.roll_pasivo = roll_pasivo
        st.session_state.roll_activo = roll_activo
        st.session_state.roll_params = {'m': m_nom, 'a': a}

    if 'roll_pasivo' in st.session_state and 'roll_activo' in st.session_state:
        roll_pasivo = st.session_state.roll_pasivo
        roll_activo = st.session_state.roll_activo
        m_saved = st.session_state.roll_params['m']
        a_saved = st.session_state.roll_params['a']
        
        t1, t2 = st.tabs(["Movimiento de saldos Consolidado por Clase", "Detalle por Contrato individual"])
        
        with t1:
            st.subheader("Movimiento de saldos Consolidado (Vertical) - Pasivos")
            if roll_pasivo:
                df_pas = pd.DataFrame(roll_pasivo)
                res_pasivo = df_pas.groupby('Clase_Activo').sum(numeric_only=True).T
                res_pasivo['TOTAL PASIVO'] = res_pasivo.sum(axis=1)
                st.dataframe(res_pasivo.style.format(precision=0, thousands="."))
                
                st.subheader("Movimiento de saldos Consolidado (Vertical) - Activos ROU")
                df_act = pd.DataFrame(roll_activo)
                res_activo = df_act.groupby('Clase_Activo').sum(numeric_only=True).T
                res_activo['TOTAL ACTIVO'] = res_activo.sum(axis=1)
                st.dataframe(res_activo.style.format(precision=0, thousands="."))
                
            else:
                st.info("No hay datos")
    
        with t2:
            if roll_pasivo:
                st.subheader("Pasivos por Arrendamiento (Detalle)")
                st.dataframe(df_pas.style.format(precision=0, thousands="."))
                st.download_button("Exportar Pasivos", to_excel(df_pas), f"RPasivos_{m_saved}_{a_saved}.xlsx")
                
                st.subheader("Activos por Derecho de Uso ROU (Detalle)")
                st.dataframe(df_act.style.format(precision=0, thousands="."))
                st.download_button("Exportar Activos", to_excel(df_act), f"RActivos_{m_saved}_{a_saved}.xlsx")

def modulo_dashboard():
    st.header("🧮 Panel de Saldos")
    
    c1, c2, c3 = st.columns(3)
    empresas = ["Todas"] + EMPRESAS_LISTA
    emp_sel = c1.selectbox("Empresa", empresas, key="dash_emp")
    m = c2.selectbox("Mes", MESES_LISTA, key="dash_m")
    a = c3.number_input("Año", value=date.today().year, key="dash_a")
    
    if st.button("Generar Resumen de Saldos", type="primary"):
        f_t = pd.to_datetime(date(a, MESES_LISTA.index(m)+1, 1)) + relativedelta(day=31)
        df_c = pd.DataFrame(cargar_contratos())
        
        if df_c.empty:
            st.session_state.dash_data = None
            st.warning("No hay contratos registrados.")
        else:
            res = []
            for _, c in df_c.iterrows():
                if emp_sel != "Todas" and c['Empresa'] != emp_sel: continue
                if f_t < pd.to_datetime(c['Inicio']).replace(day=1): continue
                
                # Excluir contratos dados de baja antes de la fecha de reporte
                if c.get('Fecha_Baja') and c['Estado'] == 'Baja':
                    f_baja = pd.to_datetime(c['Fecha_Baja'])
                    if f_baja <= f_t: continue
                
                tab, vp, rou = obtener_motor_financiero(c)
                if tab.empty or 'Fecha' not in tab.columns: continue
                past = tab[tab['Fecha'] <= f_t]
                if not past.empty:
                    tc = obtener_tc_cache(c['Moneda'], f_t); ratio_pasivo = tc
                    v_act = past.iloc[-1]['S_Fin_Orig']
                    
                    futuros = tab[tab['Fecha'] > f_t].copy()
                    v_cor_sum = 0
                    v_noc_sum_raw = 0
                    if not futuros.empty:
                        limite_12_dash = f_t + relativedelta(months=12)
                        
                        # Capital puro del periodo = S_Ini_Orig - S_Fin_Orig
                        futuros['Capital'] = futuros['S_Ini_Orig'] - futuros['S_Fin_Orig']
                        
                        # La ultima fila debe agregar todo el S_Fin_Orig remanente a su capital (ajuste del motor original)
                        futuros.iloc[-1, futuros.columns.get_loc('Capital')] += futuros.iloc[-1]['S_Fin_Orig']
                        
                        dias_al_pago = (futuros['Fecha'] - f_t).dt.days
                        es_corriente_mask = (dias_al_pago <= 90) | (futuros['Fecha'] <= limite_12_dash)
                        
                        v_cor_sum = futuros.loc[es_corriente_mask, 'Capital'].sum()
                        v_noc_sum_raw = futuros.loc[~es_corriente_mask, 'Capital'].sum()
                                
                    # El Pasivo Total debe ser exactamente el balance de cierre actual (v_act)
                    # El Pasivo Corriente son las amortizaciones estrictas de los proximos 12 meses
                    # El Pasivo No Corriente absorbe cualquier diferencia (ej. remediciones futuras)
                    v12 = v_act - v_cor_sum 
                    
                    tc_ini = float(c['Valor_Moneda_Inicio']) if float(c['Valor_Moneda_Inicio']) > 0 else 1.0

                    amort_acum = past['Dep_Orig'].sum()
                    rou_bruto = rou * tc_ini
                    amort_clp = amort_acum * tc_ini

                    res.append({
                        "Empresa": c['Empresa'], 
                        "Nombre": c['Nombre'], 
                        "ID_Contrato": c['Codigo_Interno'],
                        "Clase_Activo": c['Clase_Activo'],
                        "Moneda": c['Moneda'],
                        "Fecha Inicial": c['Inicio'],
                        "Fecha Final": c['Fin'],
                        "Valor Cuota (Moneda Orig)": c['Canon'],
                        "Cuotas Devengadas": len(past),
                        "Cuotas por Devengar": len(tab) - len(past),
                        "Valor Inicial ROU": rou * tc_ini,
                        "Tasa Anual": f"{c['Tasa']*100:.2f}%",
                        "Plazo Meses": c['Plazo'],
                        "ROU Bruto": rou_bruto,
                        "Amort. Acum": amort_clp,
                        "ROU Neto": rou_bruto - amort_clp, 
                        "Pasivo Total": v_act * ratio_pasivo,
                        "Pasivo Corriente": v_cor_sum * ratio_pasivo, 
                        "Pasivo No Corr": v12 * ratio_pasivo,
                        "Descripción 1": c['Costos_Directos'],
                        "Descripción 2": c['Pagos_Anticipados'],
                        "Descripción 3": c['Costos_Desmantelamiento'],
                        "Descripción 4": c['Incentivos']
                    })
            
            if res:
                st.session_state.dash_data = pd.DataFrame(res)
                st.session_state.dash_params = {'m': m, 'a': a, 'emp': emp_sel}
            else:
                st.session_state.dash_data = pd.DataFrame() # Vacío pero instanciado
                st.session_state.dash_params = {'m': m, 'a': a, 'emp': emp_sel}
    
    # Renderizado condicional basado en session_state
    if 'dash_data' in st.session_state and st.session_state.dash_data is not None:
        df_res = st.session_state.dash_data
        m_saved = st.session_state.dash_params['m']
        a_saved = st.session_state.dash_params['a']
        
        t1, t2 = st.tabs(["Resumen Consolidado", "Detalle por Contrato"])
        
        with t1:
            if not df_res.empty:
                cols_to_sum = ['Valor Inicial ROU', 'ROU Bruto', 'Amort. Acum', 'ROU Neto', 'Pasivo Total', 'Pasivo Corriente', 'Pasivo No Corr']
                df_grp = df_res.groupby('Empresa')[cols_to_sum].sum(numeric_only=True).reset_index()
                
                # Agregar fila de TOTALES si están "Todas" seleccionadas (es decir, hay más de 1 empresa o se seleccionó 'Todas')
                if len(df_grp) > 1 or st.session_state.dash_params.get('emp') == "Todas":
                    total_row = df_grp[cols_to_sum].sum().to_frame().T
                    total_row['Empresa'] = 'TOTALES'
                    df_grp = pd.concat([df_grp, total_row], ignore_index=True)

                # Eliminar "Valor Inicial ROU" de la vista consolidada a pedido del usuario
                if 'Valor Inicial ROU' in df_grp.columns:
                    df_grp = df_grp.drop(columns=['Valor Inicial ROU'])

                st.dataframe(df_grp.style.format(precision=0, thousands="."))
                st.download_button("Exportar Resumen Consolidado (Excel)", to_excel(df_grp), f"Resumen_Saldos_{m_saved}_{a_saved}.xlsx")
            else:
                st.info("No hay datos para esta selección.")
                
        with t2:
            if not df_res.empty:
                st.dataframe(df_res.style.format(precision=0, thousands="."))
                st.download_button("Exportar Detalle (Excel)", to_excel(df_res), f"Resumen_Saldos_Detalle_{m_saved}_{a_saved}.xlsx")

def modulo_monedas():
    st.header("💱 Monedas")
    t1, t2, t3 = st.tabs(["Carga Manual", "Carga Masiva", "Ver Todos los Datos"])
    
    with t1:
        f, m, v = st.date_input("Fecha"), st.selectbox("Moneda", ["UF", "USD"]), st.number_input("Valor CLP")
        if st.button("Guardar Moneda"): 
            insertar_moneda(f.strftime('%Y-%m-%d'), m, v)
            if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
            st.rerun()
        
    with t2:
        st.subheader("Carga Masiva de Tipos de Cambio")
        plantilla_m = pd.DataFrame(columns=["fecha", "moneda", "valor"])
        st.download_button("Descargar Plantilla", to_excel(plantilla_m), "plantilla_monedas.xlsx")
        
        arch_m = st.file_uploader("Subir Plantilla de Monedas", type=["xlsx"])
        if arch_m is not None:
            if st.button("Cargar Tipos de Cambio"):
                try:
                    df_in_m = pd.read_excel(arch_m)
                    cargar_masivo_monedas(df_in_m)
                    if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
                    st.success("Tipos de cambio cargados exitosamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error procesando archivo de monedas: {e}")
                    
    with t3:
        st.subheader("Histórico Completo de Tipos de Cambio")
        st.dataframe(cargar_monedas(), use_container_width=True)

def modulo_contratos():
    st.header("📝 Contratos")
    t1, t2, t3, t4, t5 = st.tabs(["Manual", "Masiva", "Ver Todos los Datos", "Modificación Contrato", "Baja Anticipada"])
    
    with t1:
        with st.form("f"):
            c1, c2, c3 = st.columns(3)
            emp = c1.selectbox("Empresa", EMPRESAS_LISTA)
            clase = c1.selectbox("Clase", CLASES_ACTIVO)
            prov = c1.text_input("Proveedor")
            nom, id_p = c1.text_input("Nombre Contrato"), c1.text_input("ID/RUT")
            
            mon, can = c2.selectbox("Moneda", ["CLP", "UF", "USD"]), c2.number_input("Canon")
            tas = c2.number_input("Tasa Anual %", value=6.0)
            f_i, f_f = c2.date_input("Inicio"), c2.date_input("Fin")
            t_pago = c2.selectbox("Tipo de Pago", ["Vencido", "Anticipado"])
            
            # Descripciones ocultadas a pedido del usuario, se pasan como 0 por defecto.
            cd = 0.0
            pa = 0.0
            cdesm = 0.0
            inc = 0.0
            
            if st.form_submit_button("Registrar"):
                p = (f_f.year - f_i.year)*12 + (f_f.month - f_i.month) + 1
                insertar_contrato({
                    "Codigo_Interno": generar_codigo_correlativo(emp, cargar_contratos()), 
                    "Empresa": emp, "Clase_Activo": clase, "ID": id_p, "Proveedor": prov, 
                    "Cod1": "", "Cod2": "", "Nombre": nom, "Moneda": mon, "Canon": can, 
                    "Tasa": tas/100, "Tasa_Mensual": pow(1+tas/100, 1/12)-1, 
                    "Valor_Moneda_Inicio": obtener_tc_cache(mon, f_i), "Plazo": p, 
                    "Inicio": f_i.strftime('%Y-%m-%d'), "Fin": f_f.strftime('%Y-%m-%d'), 
                    "Estado": "Activo", "Tipo_Pago": t_pago, 
                    "Costos_Directos": cd, "Pagos_Anticipados": pa, 
                    "Costos_Desmantelamiento": cdesm, "Incentivos": inc
                })
                if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
                st.success("Contrato creado manualmente")
                st.rerun()

    with t2:
        st.subheader("Carga Masiva de Contratos")
        st.write("❗ **Instrucciones para la plantilla:**")
        st.write("- **Empresa**: Debe coincidir exacto. Ej: Holdco, Pacifico")
        st.write("- **Clase_Activo**: Oficinas, Vehículos, Maquinaria, Bodegas, Inmuebles")
        st.write("- **Moneda**: CLP, UF, USD")
        st.write("- **Tipo_Pago**: Vencido, Anticipado")
        
        # Plantilla con valores de ejemplo para guiar al usuario
        df_ejemplo = pd.DataFrame([
            {"Empresa": "Holdco", "Clase_Activo": "Oficinas", "ID": "76.123.456-7", "Proveedor": "Inmobiliaria SPA", "Nombre": "Oficina Central", "Moneda": "UF", "Canon": 150.5, "Tasa Anual %": 6.0, "Tipo_Pago": "Vencido", "Inicio": "2026-01-01", "Fin": "2028-12-31", "Costos_Directos": 50.0, "Pagos_Anticipados": 0, "Costos_Desmantelamiento": 100, "Incentivos": 0},
            {"Empresa": "Pacifico", "Clase_Activo": "Vehículos", "ID": "Camioneta AB12", "Proveedor": "Automotriz Leasing S.A.", "Nombre": "Leasing Vehicular", "Moneda": "CLP", "Canon": 500000, "Tasa Anual %": 4.5, "Tipo_Pago": "Anticipado", "Inicio": "2026-03-01", "Fin": "2029-03-01", "Costos_Directos": 0, "Pagos_Anticipados": 500000, "Costos_Desmantelamiento": 0, "Incentivos": 50000}
        ])
        
        st.download_button("Descargar Plantilla con Ejemplos", to_excel(df_ejemplo), "plantilla_contratos.xlsx")
        
        arch = st.file_uploader("Subir Plantilla Completa", type=["xlsx"])
        if arch is not None:
            if st.button("Procesar y Cargar Masivamente"):
                try:
                    df_in = pd.read_excel(arch).dropna(how='all')
                    contratos_existentes = cargar_contratos()
                    errores = []
                    
                    # 1. Capa de Validación Atómica
                    for i, r in df_in.iterrows():
                        f_xl = i + 2 # Fila Excel aproximada considerando cabecera
                        
                        # Revisar obligatorios
                        c_obs = ['Empresa', 'Nombre', 'Canon', 'Moneda', 'Clase_Activo', 'Inicio', 'Fin', 'Tasa Anual %']
                        for c in c_obs:
                            if c not in r or pd.isna(r[c]) or str(r[c]).strip() == "":
                                errores.append(f"Fila {f_xl}: Campo obligatorio '{c}' está vacío.")
                                
                        if any(f"Fila {f_xl}:" in e for e in errores): continue
                        
                        # Revisar Numéricos
                        try:
                            float(r['Canon'])
                            float(r['Tasa Anual %'])
                        except ValueError:
                            errores.append(f"Fila {f_xl}: 'Canon' o 'Tasa Anual %' no son un número válido.")
                            
                        # Revisar Fechas lógicas
                        try:
                            f_i = pd.to_datetime(r['Inicio'])
                            f_f = pd.to_datetime(r['Fin'])
                            if f_i.year < 2000:
                                errores.append(f"Fila {f_xl}: Año de Inicio no puede ser menor a 2000.")
                            if f_i > f_f:
                                errores.append(f"Fila {f_xl}: La fecha de Inicio es mayor a la fecha de Fin.")
                        except Exception:
                            errores.append(f"Fila {f_xl}: Formato de fecha inválido en 'Inicio' o 'Fin'.")
                            
                    if errores:
                        st.error("🚨 **Carga Denegada:** Se encontraron errores en la plantilla. No se ha ingresado NINGÚN contrato a la base de datos.")
                        for e in errores:
                            st.warning(e)
                    else:
                        # 2. Inserción Segura
                        for _, r in df_in.iterrows():
                            emp = str(r['Empresa'])
                            f_i = pd.to_datetime(r['Inicio'])
                            f_f = pd.to_datetime(r['Fin'])
                            p = (f_f.year - f_i.year)*12 + (f_f.month - f_i.month) + 1
                            t_an = float(r['Tasa Anual %'])
                            mon = str(r['Moneda'])
                            
                            insertar_contrato({
                                "Codigo_Interno": generar_codigo_correlativo(emp, contratos_existentes), 
                                "Empresa": emp, "Clase_Activo": str(r['Clase_Activo']), "ID": str(r.get('ID', '')), 
                                "Proveedor": str(r.get('Proveedor', '')), "Cod1": "", "Cod2": "", "Nombre": str(r['Nombre']), 
                                "Moneda": mon, "Canon": float(r['Canon']), "Tasa": t_an/100, 
                                "Tasa_Mensual": pow(1+t_an/100, 1/12)-1, 
                                "Valor_Moneda_Inicio": obtener_tc_cache(mon, f_i), "Plazo": p, 
                                "Inicio": f_i.strftime('%Y-%m-%d'), "Fin": f_f.strftime('%Y-%m-%d'), 
                                "Estado": "Activo", 
                                "Tipo_Pago": str(r.get('Tipo_Pago', 'Vencido')).strip().capitalize(), 
                                "Costos_Directos": float(r.get('Costos_Directos', 0.0) if pd.notna(r.get('Costos_Directos')) else 0.0), 
                                "Pagos_Anticipados": float(r.get('Pagos_Anticipados', 0.0) if pd.notna(r.get('Pagos_Anticipados')) else 0.0), 
                                "Costos_Desmantelamiento": float(r.get('Costos_Desmantelamiento', 0.0) if pd.notna(r.get('Costos_Desmantelamiento')) else 0.0), 
                                "Incentivos": float(r.get('Incentivos', 0.0) if pd.notna(r.get('Incentivos')) else 0.0)
                            })
                            contratos_existentes.append({"Empresa": emp}) # Trick for correlation code
                        if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
                        st.success("✅ **Contratos validados y cargados exitosamente**")
                except Exception as e:
                    st.error(f"Error procesando archivo: {e}")

    with t3:
        st.subheader("Base de Datos Completa: Contratos")
        df_contratos = pd.DataFrame(cargar_contratos())
        if not df_contratos.empty:
            # Ocultando columnas de descripciones a pedido del usuario
            cols_to_drop = ['Costos_Directos', 'Pagos_Anticipados', 'Costos_Desmantelamiento', 'Incentivos']
            df_display = df_contratos.drop(columns=[col for col in cols_to_drop if col in df_contratos.columns])
            st.dataframe(df_display, use_container_width=True)
            st.download_button("Exportar Contratos (Excel)", to_excel(df_display), "Base_Contratos_Completa.xlsx")
        else:
            st.info("No hay contratos cargados.")

    with t4:
        st.subheader("Modificación de Contrato Existente")
        contratos_activos = [c for c in cargar_contratos() if c['Estado'] == 'Activo']
        if contratos_activos:
            mapa_c = {f"{c['Codigo_Interno']} - {c['Nombre']}": c for c in contratos_activos}
            sel = st.selectbox("Seleccione el Contrato a Modificar", list(mapa_c.keys()))
            c_sel = mapa_c[sel]
            
            st.write(f"**Condiciones Actuales:** Canon: {c_sel['Canon']} | Tasa Anual: {c_sel['Tasa']*100:.2f}% | Plazo Actual: {c_sel['Plazo']} meses")
            
            with st.form("f_rem"):
                st.write("Determine las nuevas condiciones de renovación o alteración del contrato.")
                c1, c2, c3 = st.columns(3)
                n_can = c1.number_input("Nuevo Canon", value=float(c_sel['Canon']))
                n_tas = c2.number_input("Nueva Tasa Anual %", value=float(c_sel['Tasa']*100))
                n_fin = c3.date_input("Nueva Fecha Fin", value=pd.to_datetime(c_sel['Fin']))
                
                f_rem = st.date_input("Fecha Efectiva de Registro (Modificación)", value=date.today())
                
                if st.form_submit_button("Aplicar Modificación"):
                    f_i = pd.to_datetime(c_sel['Inicio'])
                    f_rem_dt = pd.to_datetime(f_rem)
                    
                    if f_rem_dt <= f_i:
                        st.error("La fecha de modificación debe ser estrictamente posterior a la fecha de inicio original.")
                        st.stop()
                        
                    # Simulamos el contrato hasta la fecha de remedición para obtener los saldos de corte
                    tab_old, vp_old, rou_old = obtener_motor_financiero(c_sel)
                    
                    past_tab = tab_old[tab_old['Fecha'] < f_rem_dt]
                    if past_tab.empty:
                        st.error("La fecha seleccionada no permite capturar saldos históricos.")
                        st.stop()
                        
                    old_pasivo_orig = past_tab.iloc[-1]['S_Fin_Orig']
                    old_amort_acum_orig = past_tab['Dep_Orig'].sum()
                    old_rou_net_orig = rou_old - old_amort_acum_orig
                    
                    tc_ini = float(c_sel['Valor_Moneda_Inicio']) if float(c_sel['Valor_Moneda_Inicio']) > 0 else 1.0
                    tc_f_rem = obtener_tc_cache(c_sel['Moneda'], f_rem_dt)
                    if tc_f_rem == 0: tc_f_rem = 1.0
                    
                    # Cálculo del Puente (Ajuste ROU base funcional)
                    ajuste_rou_uf = old_pasivo_orig - old_rou_net_orig * (tc_ini / tc_f_rem)
                    
                    n_p = (n_fin.year - f_rem_dt.year)*12 + (n_fin.month - f_rem_dt.month) + 1
                    t_m = pow(1+n_tas/100, 1/12)-1
                    
                    from db import insertar_remedicion, actualizar_contrato_remedicion
                    
                    # 1. Registrar el evento en el historial de remediciones
                    insertar_remedicion(c_sel['Codigo_Interno'], f_rem.strftime('%Y-%m-%d'), n_can, n_tas/100, t_m, n_fin.strftime('%Y-%m-%d'), n_p, ajuste_rou_uf)
                    
                    # 2. Actualizar la cabecera del contrato original con la nueva fecha de madurez, para que los filtros de app sigan viéndolo activo hasta n_fin
                    # Importante: No machacamos Inicio, Canon base ni VP original. Solo los parámetros que avisan cuándo termina.
                    actualizar_contrato_remedicion(c_sel['Codigo_Interno'], c_sel['Canon'], c_sel['Tasa'], c_sel['Tasa_Mensual'], n_fin.strftime('%Y-%m-%d'), c_sel['Plazo']+n_p, f_rem.strftime('%Y-%m-%d'))
                    
                    st.success(f"¡Contrato {c_sel['Codigo_Interno']} modificado exitosamente! (Se agregó el tramo de modificación a su flujo histórico)")
                    # Limpiar estado del motor financiero para forzar re-cálculo
                    if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("No hay contratos activos.")
            
    with t5:
        st.subheader("Baja Anticipada de Contrato")
        if 'contratos_activos' in locals() and contratos_activos:
            sel_b = st.selectbox("Seleccione Contrato para Baja", list(mapa_c.keys()), key="sbaja")
            c_baja = mapa_c[sel_b]
            f_baja = st.date_input("Fecha Efectiva de Baja", value=pd.to_datetime(c_baja['Fin']))
            if st.button("Procesar Baja Definitiva"):
                dar_baja_contrato(c_baja['Codigo_Interno'], f_baja.strftime('%Y-%m-%d'))
                if 'motor_cache' in st.session_state: st.session_state.motor_cache.clear()
                st.success(f"Contrato dado de baja exitosamente en la fecha {f_baja}")
                st.rerun()

def modulo_vencimientos():
    st.header("📝 Notas a los Estados Financieros")
    
    st.write("Esta nota revela el **Riesgo de Liquidez** al mostrar la salida futura bruta nominal de caja, clasificada por rangos de vencimiento. No incluye el descuento financiero, por lo tanto la suma difiere del Pasivo en Balance.")
    
    c1, c2, c3 = st.columns(3)
    m_nom = c1.selectbox("Mes de Cierre", MESES_LISTA, key="n_mes")
    a = c2.number_input("Año de Cierre", value=date.today().year, key="n_ano")
    
    df_c = pd.DataFrame(cargar_contratos())
    if df_c.empty:
        st.info("No hay contratos registrados.")
        return
        
    empresas = ["Todas"] + df_c['Empresa'].unique().tolist()
    emp_sel = c3.selectbox("Empresa", empresas, key="n_emp")
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        btn_no_desc = st.button("Generar Pasivos No Descontados", type="primary")
    with c_btn2:
        btn_desc = st.button("Generar Pasivos Descontados", type="primary")
        
    if btn_no_desc or btn_desc:
        es_desc = btn_desc
        f_t = pd.to_datetime(date(a, MESES_LISTA.index(m_nom)+1, 1)) + relativedelta(day=31)
        res = []
        for _, c in df_c.iterrows():
            if emp_sel != "Todas" and c['Empresa'] != emp_sel: continue
            if f_t < pd.to_datetime(c['Inicio']).replace(day=1): continue
            
            # Si el contrato fue dado de baja antes o durante el mes de reporte, saltarlo
            if c.get('Fecha_Baja') and c['Estado'] == 'Baja':
                f_baja = pd.to_datetime(c['Fecha_Baja'])
                if f_baja <= f_t: continue
                
            tab, _, _ = obtener_motor_financiero(c)
            if tab.empty or 'Fecha' not in tab.columns: continue
            # Solo los flujos estrictamente futuros al cierre
            futuros = tab[tab['Fecha'] > f_t]
            if futuros.empty: continue
            
            # Para que cuadre perfectamente con el saldo contable en "Pasivos Descontados",
            # el monto a distribuir en los buckets debe ser la cuota de capital real deducida u o calculada 
            # desde la amortización del pasivo original.
            # Recordar que Capital_Mes = Pago_Orig - Int_Orig  (Lo que disminuye S_Fin_Orig)
            # Para la primera cuota corriente del mes siguiente, S_Ini_Orig es el Saldo del Pasivo Total de HOY.
            
            # saldo_remanente_hoy es la fotografia real de pasivo en el balance a f_t
            saldo_remanente_hoy = tab[tab['Fecha'] <= f_t].iloc[-1]['S_Fin_Orig'] if not tab[tab['Fecha'] <= f_t].empty else tab.iloc[0]['S_Ini_Orig']
            
            tc = obtener_tc_cache(c['Moneda'], f_t)
            
            ultima_fecha = futuros.iloc[-1]['Fecha']
            
            if es_desc:
                # La disminución del pasivo que genera esta cuota es: (S_Ini_Orig - S_Fin_Orig).
                futuros['Capital'] = futuros['S_Ini_Orig'] - futuros['S_Fin_Orig']
                # La ultima fila debe agregar todo el S_Fin_Orig remanente a su capital
                futuros.iloc[-1, futuros.columns.get_loc('Capital')] += futuros.iloc[-1]['S_Fin_Orig']
                suma_distribuida_orig = futuros['Capital'].sum()
                futuros['Monto_Bruto'] = futuros['Capital'] * tc
            else:
                futuros['Monto_Bruto'] = futuros['Pago_Orig'] * tc
                suma_distribuida_orig = 0
                
            limite_12m = f_t + relativedelta(months=12)
            
            # Vectorized assignment of es_corriente
            dias_pago = (futuros['Fecha'] - f_t).dt.days
            futuros['es_corriente'] = (dias_pago <= 90) | (futuros['Fecha'] <= limite_12_dash if 'limite_12_dash' in locals() else futuros['Fecha'] <= limite_12m)
            
            # Vectorized Assignment of Buckets
            bins = [-float('inf'), 90, 1095, 2555, float('inf')] # 90 days, 3 years, 7 years, >7 years
            # Corriente > 90 will be handled by boolean logic overrides later to mix date and day rules
            
            # Fallback direct assignment via map/apply for complex overlapping logic (small dataframe per contract usually)
            def assign_bucket(row):
                d = (row['Fecha'] - f_t).days
                if row['es_corriente']:
                    if d <= 90: return ('90 días', 1)
                    else: return ('90 días a 1 año', 2)
                else:
                    if d <= 1095: return ('2 a 3 años', 3)
                    elif d <= 2555: return ('4 a 7 años', 4)
                    else: return ('Más de 7 años', 5)
            
            buckets_ord = futuros.apply(assign_bucket, axis=1)
            futuros['Bucket'] = [b[0] for b in buckets_ord]
            futuros['Orden'] = [b[1] for b in buckets_ord]
            
            # Extraer dict para procesar el residuo contable final
            cuotas_temp = futuros[['Fecha', 'Bucket', 'Orden', 'Monto_Bruto', 'es_corriente']].to_dict('records')
            # Fix naming para compatibilidad
            for d in cuotas_temp: 
                d['Monto'] = d.pop('Monto_Bruto')
                d['ID_Contrato'] = c['Codigo_Interno']
                d['Nombre'] = c['Nombre']
                d['Clase_Activo'] = c['Clase_Activo']
            
            if es_desc and cuotas_temp:
                diferencia_residual = saldo_remanente_hoy - suma_distribuida_orig
                if abs(diferencia_residual) > 0.01:
                    cuota_lejana = max(cuotas_temp, key=lambda x: x['Orden'])
                    cuota_lejana['Monto'] += (diferencia_residual * tc)
                    
            res.extend(cuotas_temp)
        
        if not res:
            st.session_state.venc_data = pd.DataFrame() # DataFrame vacío
        else:
            st.session_state.venc_data = pd.DataFrame(res)
            
        st.session_state.venc_params = {'m': m_nom, 'a': a, 'f_t': f_t, 'es_desc': es_desc}

    if 'venc_data' in st.session_state:
        df_res = st.session_state.venc_data
        m_saved = st.session_state.venc_params['m']
        a_saved = st.session_state.venc_params['a']
        f_t_saved = st.session_state.venc_params['f_t']
        es_desc_saved = st.session_state.venc_params.get('es_desc', False)
        tipo_lbl = "descontados" if es_desc_saved else "no descontados"
        
        if df_res.empty:
            st.warning(f"No hay flujos futuros a rendir (Pasivos {tipo_lbl} = 0).")
            return
            
        todas_cols = ['90 días', '90 días a 1 año', 'Total Corriente', '2 a 3 años', '4 a 7 años', 'Más de 7 años', 'Total No Corriente']
        
        t1, t2 = st.tabs(["Consolidado por Clase", "Detalle por Contrato individual"])
        
        with t1:
            st.subheader(f"Pasivos {tipo_lbl} (Consolidado)")
            piv = df_res.groupby(['Clase_Activo', 'Bucket', 'Orden'])['Monto'].sum().unstack(['Bucket', 'Orden']).fillna(0)
            piv.columns = [col[0] for col in piv.columns.to_flat_index()]
            
            piv['Total Corriente'] = piv.get('90 días', 0) + piv.get('90 días a 1 año', 0)
            piv['Total No Corriente'] = piv.get('2 a 3 años', 0) + piv.get('4 a 7 años', 0) + piv.get('Más de 7 años', 0)
            
            cols_finales = [c for c in todas_cols if c in piv.columns]
            piv = piv[cols_finales]
            
            piv = piv / 1000
            piv.loc['Total'] = piv.sum()
            
            st.write(f"**Detalle al {f_t_saved.strftime('%d-%m-%Y')} (En M$)**")
            st.dataframe(piv.style.format(precision=0, thousands="."))
            st.download_button("Exportar Consolidado (Excel)", to_excel(piv), f"Nota_Venc_Consolidado_{m_saved}_{a_saved}.xlsx")
    
        with t2:
            st.subheader(f"Pasivos {tipo_lbl} (Detallado)")
            piv2 = df_res.groupby(['ID_Contrato', 'Nombre', 'Clase_Activo', 'Bucket', 'Orden'])['Monto'].sum().unstack(['Bucket', 'Orden']).fillna(0)
            piv2.columns = [col[0] for col in piv2.columns.to_flat_index()]
            
            piv2['Total Corriente'] = piv2.get('90 días', 0) + piv2.get('90 días a 1 año', 0)
            piv2['Total No Corriente'] = piv2.get('2 a 3 años', 0) + piv2.get('4 a 7 años', 0) + piv2.get('Más de 7 años', 0)
            
            cols_finales2 = [c for c in todas_cols if c in piv2.columns]
            piv2 = piv2[cols_finales2]
            
            piv2 = piv2 / 1000
            st.write(f"**Detalle Contractual al {f_t_saved.strftime('%d-%m-%Y')} (En M$)**")
            st.dataframe(piv2.style.format(precision=0, thousands="."))
            st.download_button("Exportar Detalle (Excel)", to_excel(piv2), f"Nota_Venc_Detalle_{m_saved}_{a_saved}.xlsx")


def modulo_auditoria():
    st.header("🔍 Auditoría y Transparencia")
    t1, t2 = st.tabs(["Fórmulas y Criterios", "Descarga de Datos Crudos"])
    
    with t1:
        st.subheader("Criterios Matemáticos de Cálculo IFRS 16")
        st.markdown('''
        **Motor Financiero V21.0 - Estándar IFRS 16**
        
        1. **Conversión de Tasa de Interés (Tasa Efectiva Mensual)**
        Se utiliza la fórmula de interés compuesto para hallar la tasa mensual equivalente a partir del input anual:
        `Tasa_Mensual = (1 + Tasa_Anual) ^ (1/12) - 1`
        *(Nota: Si se desea una validación lineal con calculadoras Excel estándar, se requiere proveer la tasa Nominal y no la Efectiva)*
        
        2. **Cálculo de Valor Presente (VP) - Pagos Vencidos**
        `VP = Canon * [1 - (1 + Tasa_Mensual)^(-Plazo)] / Tasa_Mensual`
        
        3. **Cálculo de Valor Presente (VP) - Pagos Anticipados**
        `VP = Canon * [1 - (1 + Tasa_Mensual)^(-Plazo)] / Tasa_Mensual * (1 + Tasa_Mensual)`
        
        4. **Cálculo del Activo por Derecho de Uso (ROU Inicial)**
        `ROU = VP + Costos_Directos_Iniciales + Pagos_Anticipados_Extra + Costos_Desmantelamiento - Incentivos`
        
        5. **Amortización Mensual (Línea Recta)**
        `Amortización = ROU_Inicial / Plazo`
        
        6. **Devengo de Intereses (Interés Efectivo)**
        `Interés_Mes = Saldo_Inicial_Capital * Tasa_Mensual` (Para vencidos)
        `Interés_Mes = (Saldo_Inicial_Capital - Canon) * Tasa_Mensual` (Para anticipados)
        
        7. **Cálculo de Pasivos No Descontados (Análisis de Vencimientos NIIF 16)**
        Se utiliza para la nota obligatoria de riesgo de liquidez NIIF 7. Corresponde al sumatorio estricto de todos los desembolsos nominales brutos (`Canon * Tipo_Cambio_Cierre`) cuyas fechas de pago sean posteriores a la fecha de reporte, sin aplicar la tasa de descuento.
        `Pasivo_No_Descontado_Bucket_A = SUMA(Cánones_Futuros_Rango_A) * TC_Cierre`
        ''')
    
    with t2:
        st.subheader("Extracción de Data en Bruto")
        st.info("Descarga la base de datos subyacente de contratos activos para trazar los cálculos uno a uno en Excel.")
        df = pd.DataFrame(cargar_contratos())
        if not df.empty:
            st.download_button(
                label="📥 Descargar Base Completa Contratos",
                data=to_excel(df),
                file_name="Auditoria_Contratos_Bruto.xlsx"
            )

def modulo_configuracion():
    st.header("⚙️ Configuración del Sistema")
    t1, t2, t3, t4, t5 = st.tabs(["Usuarios", "Empresas", "Clases de Activo", "Cuentas Contables y Numeración", "Mantenimiento de Base de Datos"])
    
    with t1:
        st.subheader("Gestión de Usuarios")
        c1, c2 = st.columns(2)
        n_user = c1.text_input("Nuevo Usuario")
        n_pass = c1.text_input("Contraseña", type="password")
        if c1.button("Crear/Actualizar Usuario"):
            agregar_usuario(n_user, n_pass)
            st.success("Usuario ingresado con éxito.")
            st.rerun()
            
        st.write("Usuarios Actuales en Sistema:")
        usr_df = pd.DataFrame(obtener_usuarios(), columns=["Usuario"])
        st.dataframe(usr_df)
        
        st.subheader("Eliminar Usuario")
        del_usr = st.selectbox("Seleccione Usuario a Eliminar", [""] + usr_df["Usuario"].tolist())
        if st.button("Eliminar", key="del_usr_btn") and del_usr != "":
            conn = conectar()
            conn.execute("DELETE FROM usuarios WHERE usuario=?", (del_usr,))
            conn.commit(); conn.close()
            st.success(f"Usuario {del_usr} eliminado con éxito.")
            st.rerun()
        
    with t2:
        st.subheader("Sociedades / Empresas")
        c1, c2 = st.columns(2)
        nueva_empresa = c1.text_input("Nombre de la Nueva Empresa")
        if c1.button("Agregar Empresa"):
            agregar_parametro('EMPRESA', nueva_empresa.strip())
            st.success("Empresa ingresada con éxito.")
            st.rerun()
            
        st.write("Empresas Activas:")
        emp_df = pd.DataFrame(obtener_parametros('EMPRESA'), columns=["Empresa_Registrada"])
        st.dataframe(emp_df)
        
        st.subheader("Modificar / Eliminar Empresa")
        c3, c4 = st.columns(2)
        del_emp = c3.selectbox("Seleccione Empresa a Eliminar", [""] + emp_df["Empresa_Registrada"].tolist())
        if c3.button("Eliminar", key="del_emp_btn") and del_emp != "":
            eliminar_parametro('EMPRESA', del_emp)
            st.success(f"Empresa '{del_emp}' eliminada.")
            st.rerun()
            
        mod_emp_old = c4.selectbox("Seleccione Empresa a Renombrar", [""] + emp_df["Empresa_Registrada"].tolist())
        mod_emp_new = c4.text_input("Nuevo Nombre", key="new_n_emp")
        if c4.button("Renombrar Empresa") and mod_emp_old != "" and mod_emp_new.strip() != "":
            conn = conectar()
            # Renombrar en la config
            conn.execute("UPDATE config_params SET valor=? WHERE tipo='EMPRESA' AND valor=?", (mod_emp_new.strip(), mod_emp_old))
            # Actualizar todos los contratos asociados a esta empresa
            conn.execute("UPDATE contratos SET Empresa=? WHERE Empresa=?", (mod_emp_new.strip(), mod_emp_old))
            conn.commit(); conn.close()
            st.success("Empresa actualizada con éxito.")
            st.rerun()
        
    with t3:
        st.subheader("Clases de Activo")
        c1, c2 = st.columns(2)
        nueva_clase = c1.text_input("Ingresar Nueva Clase")
        if c1.button("Agregar Clase"):
            agregar_parametro('CLASE_ACTIVO', nueva_clase.strip())
            st.success("Clase de activo ingresada con éxito.")
            st.rerun()
            
        st.write("Clases Activas:")
        cls_df = pd.DataFrame(obtener_parametros('CLASE_ACTIVO'), columns=["Clase_Registrada"])
        st.dataframe(cls_df)
        
        st.subheader("Modificar / Eliminar Clase")
        c3, c4 = st.columns(2)
        del_cls = c3.selectbox("Seleccione Clase a Eliminar", [""] + cls_df["Clase_Registrada"].tolist())
        if c3.button("Eliminar", key="del_cls_btn") and del_cls != "":
            eliminar_parametro('CLASE_ACTIVO', del_cls)
            st.success(f"Clase '{del_cls}' eliminada.")
            st.rerun()
            
        mod_cls_old = c4.selectbox("Seleccione Clase a Renombrar", [""] + cls_df["Clase_Registrada"].tolist())
        mod_cls_new = c4.text_input("Nuevo Nombre", key="new_n_cls")
        if c4.button("Renombrar Clase") and mod_cls_old != "" and mod_cls_new.strip() != "":
            conn = conectar()
            conn.execute("UPDATE config_params SET valor=? WHERE tipo='CLASE_ACTIVO' AND valor=?", (mod_cls_new.strip(), mod_cls_old))
            conn.execute("UPDATE contratos SET Clase_Activo=? WHERE Clase_Activo=?", (mod_cls_new.strip(), mod_cls_old))
            conn.commit(); conn.close()
            st.success("Clase actualizada con éxito.")
            st.rerun()

    with t4:
        st.subheader("Traductor Plan de Cuentas Automático")
        clist = [
            ('CUENTA_ROU', 'Activo por Derecho de Uso (ROU)'), 
            ('CUENTA_PASIVO', 'Pasivo por Arrendamiento'), 
            ('CUENTA_BCO_AJUSTE', 'Banco / Provisiones (Ajustes)'), 
            ('CUENTA_GASTO_AMORT', 'Gasto Amortización ROU'), 
            ('CUENTA_AMORT_ACUM', 'Amortización Acumulada ROU'), 
            ('CUENTA_GASTO_INT', 'Gasto Interés (Costo Fin.)'), 
            ('CUENTA_BANCO_PAGO', 'Banco Efectivo (Pago)'), 
            ('CUENTA_PERDIDA_TC', 'Pérdida por Tipo de Cambio'), 
            ('CUENTA_GANANCIA_TC', 'Ganancia por Tipo de Cambio')
        ]
        with st.form("fc_cuentas"):
            n_vals = []
            st.write("Ingrese el N° de Cuenta y Nombre de Cuenta para cada tipo.")
            for k, label_default in clist:
                col1, col2 = st.columns([1, 4])
                v_num_act = obtener_parametros(k + '_NUM')[0] if obtener_parametros(k + '_NUM') else "0000"
                v_nom_act = obtener_parametros(k + '_NOM')[0] if obtener_parametros(k + '_NOM') else label_default
                n_num = col1.text_input(f"N°", value=v_num_act, key=k+'_NUM')
                n_nom = col2.text_input(label_default, value=v_nom_act, key=k+'_NOM')
                n_vals.append((k + '_NUM', n_num))
                n_vals.append((k + '_NOM', n_nom))
            
            if st.form_submit_button("Actualizar y Guardar Plan de Cuentas"):
                conn = conectar()
                for k, v in n_vals:
                    conn.execute("DELETE FROM config_params WHERE tipo=?", (k,))
                    conn.execute("INSERT INTO config_params VALUES (?,?)", (k, v))
                conn.commit(); conn.close()
                st.success("Toda la contabilización del motor IFRS ha sido enrutada a este nuevo Plan de Cuentas.")
                st.rerun()

    with t5:
        st.subheader("Mantenimiento y Reseteo de Datos")
        st.warning("⚠️ **ATENCIÓN**: Las acciones de esta sección borrarán datos operativos del sistema. Asegúrese de haber exportado lo que necesite antes de proceder. La configuración (cuentas, usuarios, empresas) NO será afectada.")
        
        st.markdown("---")
        st.write("### 💱 1. Limpieza de Monedas (Tipos de Cambio)")
        st.write("Borra todo el historial de tipos de cambio de la base de datos para cargar un nuevo archivo desde cero.")
        if st.button("🗑️ Borrar Todos los Tipos de Cambio", type="primary", key="btn_limpiar_monedas"):
            limpiar_monedas()
            st.success("✅ Historial de monedas eliminado por completo. Puede cargar un nuevo archivo en el módulo de Monedas.")
            
        st.markdown("---")
        st.write("### 📝 2. Limpieza de Contratos y Remediciones")
        st.write("Borra toda la cartera de contratos registrados y toda su historia de remediciones (trazabilidad).")
        if st.button("🚨 Borrar Todos los Contratos Registrados", type="primary", key="btn_limpiar_contratos"):
            limpiar_contratos()
            st.success("✅ Base de datos de contratos vaciada. El sistema está listo para una carga masiva desde el módulo de Contratos.")

def main():
    inicializar_db() # Garantizar que la BD exista al iniciar
    if not st.session_state.auth:
        st.title("🔐 Login Mundo 16")
        u = st.text_input("Usuario", "admin")
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if verificar_credenciales(u, p):
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    else:
        st.sidebar.title("🌍 Mundo 16")
        st.sidebar.markdown("---")
        st.sidebar.button("Salir (Cerrar Sesión)", on_click=lambda: st.session_state.update(auth=False))
        op = st.sidebar.radio("Menú Principal", ["Contratos", "Resumen de Saldos", "Asientos", "Nota: Movimiento de saldos", "Nota: Vencimientos NIIF 16", "Monedas", "Auditoría", "Configuración"])
        if op == "Monedas": modulo_monedas()
        elif op == "Contratos": modulo_contratos()
        elif op == "Resumen de Saldos": modulo_dashboard()
        elif op == "Asientos": modulo_asientos()
        elif op == "Nota: Movimiento de saldos": modulo_notas()
        elif op == "Nota: Vencimientos NIIF 16": modulo_vencimientos()
        elif op == "Auditoría": modulo_auditoria()
        elif op == "Configuración": modulo_configuracion()

if __name__ == "__main__": main()