#!/usr/bin/env python3
"""
Generator WealthReader v6 - Datos Sintéticos Basados en Estadísticas Oficiales de España

Versión que integra:
- 35 campos de la v4 (demografía, tarjetas, recibos, préstamos)
- Distribuciones basadas en INE (ECV 2024, EPF 2024, EES)
- Datos del Banco de España (EFF 2022)
- Diferencias regionales por CCAA
- 14 factores de default calibrados

Fuentes:
- INE: Encuesta de Condiciones de Vida 2024
- INE: Encuesta de Presupuestos Familiares 2024
- INE: Encuesta de Estructura Salarial
- Banco de España: Encuesta Financiera de las Familias 2022
- SERPAVI: Índices de vivienda

Autor: ScoreAI - Enero 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import argparse
import gc
from multiprocessing import Pool, cpu_count
import warnings
warnings.filterwarnings('ignore')


# =============================================================================
# CONFIGURACIÓN BASADA EN DATOS OFICIALES DE ESPAÑA
# =============================================================================

# Distribución por CCAA (INE 2024) - Población relativa
CCAA_DISTRIBUCION = {
    'Andalucía': 0.179,
    'Cataluña': 0.163,
    'Madrid': 0.143,
    'C. Valenciana': 0.107,
    'Galicia': 0.057,
    'Castilla y León': 0.050,
    'País Vasco': 0.047,
    'Canarias': 0.046,
    'Castilla-La Mancha': 0.044,
    'Murcia': 0.032,
    'Aragón': 0.028,
    'Baleares': 0.026,
    'Extremadura': 0.022,
    'Asturias': 0.021,
    'Navarra': 0.014,
    'Cantabria': 0.012,
    'La Rioja': 0.007,
    'Ceuta y Melilla': 0.002
}

# Salario medio mensual bruto por CCAA (INE EES 2024)
SALARIO_MEDIO_CCAA = {
    'País Vasco': 2809, 'Madrid': 2761, 'Navarra': 2589, 'Cataluña': 2534,
    'Asturias': 2358, 'Aragón': 2345, 'Cantabria': 2289, 'La Rioja': 2267,
    'Castilla y León': 2234, 'Baleares': 2198, 'Galicia': 2156,
    'C. Valenciana': 2089, 'Andalucía': 2034, 'Murcia': 2012,
    'Castilla-La Mancha': 1998, 'Canarias': 1987, 'Extremadura': 1923,
    'Ceuta y Melilla': 2450
}

# Tasa AROPE por CCAA (INE ECV 2024) - Riesgo de pobreza/exclusión
TASA_AROPE_CCAA = {
    'Andalucía': 0.356, 'Castilla-La Mancha': 0.342, 'Extremadura': 0.324,
    'Murcia': 0.324, 'Canarias': 0.318, 'C. Valenciana': 0.284,
    'Galicia': 0.256, 'Castilla y León': 0.234, 'Asturias': 0.228,
    'Aragón': 0.224, 'Cataluña': 0.218, 'La Rioja': 0.212,
    'Madrid': 0.198, 'Cantabria': 0.196, 'Baleares': 0.162,
    'Navarra': 0.183, 'País Vasco': 0.148, 'Ceuta y Melilla': 0.380
}

# Gasto medio por persona por CCAA (INE EPF 2024)
GASTO_MEDIO_CCAA = {
    'País Vasco': 15504, 'Madrid': 15108, 'Cataluña': 14746, 'Navarra': 14589,
    'Baleares': 14234, 'Aragón': 13876, 'Cantabria': 13654, 'Asturias': 13456,
    'La Rioja': 13234, 'Castilla y León': 12987, 'Galicia': 12654,
    'C. Valenciana': 12456, 'Andalucía': 12123, 'Castilla-La Mancha': 11876,
    'Murcia': 11620, 'Canarias': 11373, 'Extremadura': 11398,
    'Ceuta y Melilla': 12500
}

# Distribución de edad por rangos (INE Censo 2024)
DISTRIBUCION_EDAD = {
    (18, 24): 0.08,   # Jóvenes
    (25, 34): 0.14,   # Adultos jóvenes  
    (35, 44): 0.18,   # Adultos
    (45, 54): 0.19,   # Adultos maduros
    (55, 64): 0.17,   # Pre-jubilación
    (65, 74): 0.14,   # Jubilación temprana
    (75, 90): 0.10    # Mayores
}

# Estado civil por edad (INE ECH 2024)
ESTADO_CIVIL_POR_EDAD = {
    (18, 29): {'soltero': 0.85, 'casado': 0.12, 'divorciado': 0.02, 'viudo': 0.01},
    (30, 44): {'soltero': 0.35, 'casado': 0.52, 'divorciado': 0.12, 'viudo': 0.01},
    (45, 64): {'soltero': 0.12, 'casado': 0.65, 'divorciado': 0.18, 'viudo': 0.05},
    (65, 90): {'soltero': 0.06, 'casado': 0.52, 'divorciado': 0.08, 'viudo': 0.34}
}

# Categoría laboral (INE EPA 2024)
CATEGORIA_LABORAL = {
    'empleado_privado': 0.48,
    'funcionario': 0.12,
    'autonomo': 0.14,
    'jubilado': 0.18,
    'desempleado': 0.06,
    'estudiante': 0.02
}

# Distribución de ingresos por percentil (INE ECV 2024)
# Ingreso medio por persona: 14.807€ anuales
PERCENTILES_INGRESO = {
    10: 6500,   # P10
    25: 10200,  # P25
    50: 14807,  # Mediana
    75: 21500,  # P75
    90: 32000,  # P90
    95: 45000,  # P95
    99: 75000   # P99
}

# Datos patrimoniales (Banco de España EFF 2022)
PATRIMONIO_EFF = {
    'riqueza_neta_mediana': 142700,
    'riqueza_neta_media': 309000,
    'renta_mediana_hogar': 32400,
    'renta_media_hogar': 43100,
    'pct_activos_reales': 0.838,      # 83.8% hogares con activos reales
    'mediana_activos_reales': 181300,
    'pct_activos_financieros': 0.977,  # 97.7% hogares con activos financieros
    'mediana_activos_financieros': 16200,
    'pct_depositos': 0.525,            # 47.5-56.1% de activos financieros en depósitos
}

# Tenencia de vivienda por edad (EFF 2022)
VIVIENDA_POR_EDAD = {
    (18, 34): {'propietario': 0.318, 'alquiler': 0.582, 'otros': 0.10},
    (35, 44): {'propietario': 0.58, 'alquiler': 0.34, 'otros': 0.08},
    (45, 64): {'propietario': 0.78, 'alquiler': 0.16, 'otros': 0.06},
    (65, 90): {'propietario': 0.87, 'alquiler': 0.08, 'otros': 0.05}
}

# Digitalización bancaria (BCE/PwC 2024)
USO_DIGITAL = {
    'banca_online': 0.70,         # >70% usa banca online
    'bizum': 0.33,                # 1/3 usa Bizum
    'wallet': 0.12,               # 12% usa wallets
    'tarjeta_debito': 0.95,       # 95% tiene tarjeta débito
    'tarjeta_credito': 0.45       # 45% tiene tarjeta crédito
}

# Estructura del gasto familiar (INE EPF 2024)
ESTRUCTURA_GASTO = {
    'vivienda_suministros': 0.324,
    'alimentacion': 0.158,
    'transporte': 0.114,
    'restaurantes_hoteles': 0.09,
    'ocio_cultura': 0.07,
    'salud': 0.045,
    'vestido_calzado': 0.042,
    'comunicaciones': 0.032,
    'otros': 0.125
}


# =============================================================================
# ESCENARIOS ECONÓMICOS
# =============================================================================

ESCENARIOS = {
    'normal': {
        'nombre': 'Economía Estable',
        'descripcion': 'Condiciones económicas normales basadas en ECV/EPF 2024',
        'perfiles': {
            'bajo_riesgo': {'proporcion': 0.30, 'prob_default_base': 0.02},
            'medio_riesgo': {'proporcion': 0.50, 'prob_default_base': 0.15},
            'alto_riesgo': {'proporcion': 0.20, 'prob_default_base': 0.40}
        },
        'multiplicador_ingreso': 1.0,
        'multiplicador_ahorro': 1.0,
        'tasa_desempleo_adicional': 0.0
    },
    'crisis': {
        'nombre': 'Crisis Económica',
        'descripcion': 'Escenario de recesión con mayor desempleo y menor renta',
        'perfiles': {
            'bajo_riesgo': {'proporcion': 0.15, 'prob_default_base': 0.10},
            'medio_riesgo': {'proporcion': 0.45, 'prob_default_base': 0.35},
            'alto_riesgo': {'proporcion': 0.40, 'prob_default_base': 0.65}
        },
        'multiplicador_ingreso': 0.85,
        'multiplicador_ahorro': 0.60,
        'tasa_desempleo_adicional': 0.08
    },
    'boom': {
        'nombre': 'Expansión Económica',
        'descripcion': 'Crecimiento económico con mayor empleo y rentas',
        'perfiles': {
            'bajo_riesgo': {'proporcion': 0.50, 'prob_default_base': 0.01},
            'medio_riesgo': {'proporcion': 0.40, 'prob_default_base': 0.05},
            'alto_riesgo': {'proporcion': 0.10, 'prob_default_base': 0.15}
        },
        'multiplicador_ingreso': 1.15,
        'multiplicador_ahorro': 1.30,
        'tasa_desempleo_adicional': -0.03
    }
}


# =============================================================================
# CLASE PRINCIPAL DEL GENERADOR
# =============================================================================

class WealthReaderSyntheticGeneratorV6:
    """
    Generador de datos sintéticos bancarios basado en estadísticas oficiales de España.
    
    Fuentes:
    - INE: ECV, EPF, EES, EPA, Censo
    - Banco de España: EFF 2022, ECF
    - SERPAVI: Datos de vivienda
    """
    
    def __init__(self, scenario: str = 'normal', seed: int = 42):
        """
        Inicializa el generador.
        
        Args:
            scenario: 'normal', 'crisis' o 'boom'
            seed: Semilla para reproducibilidad
        """
        self.scenario = scenario
        self.config = ESCENARIOS[scenario]
        self.seed = seed
        np.random.seed(seed)
        
        # Preparar distribuciones
        self._prepare_distributions()
    
    def _prepare_distributions(self):
        """Prepara las distribuciones de probabilidad basadas en datos oficiales."""
        # CCAA
        self.ccaa_names = list(CCAA_DISTRIBUCION.keys())
        self.ccaa_probs = list(CCAA_DISTRIBUCION.values())
        
        # Categoría laboral ajustada por escenario
        cat_lab = CATEGORIA_LABORAL.copy()
        desempleo_extra = self.config['tasa_desempleo_adicional']
        if desempleo_extra != 0:
            cat_lab['desempleado'] = min(0.25, max(0.02, cat_lab['desempleado'] + desempleo_extra))
            # Reajustar otras categorías
            factor = (1 - cat_lab['desempleado']) / (1 - CATEGORIA_LABORAL['desempleado'])
            for k in cat_lab:
                if k != 'desempleado':
                    cat_lab[k] *= factor
        self.cat_lab_names = list(cat_lab.keys())
        self.cat_lab_probs = list(cat_lab.values())
    
    def _generate_age(self, n: int) -> np.ndarray:
        """Genera edades siguiendo distribución INE."""
        ages = []
        for (min_age, max_age), prob in DISTRIBUCION_EDAD.items():
            count = int(n * prob)
            ages.extend(np.random.randint(min_age, max_age + 1, count))
        
        # Ajustar al tamaño exacto
        while len(ages) < n:
            ages.append(np.random.randint(18, 90))
        return np.array(ages[:n])
    
    def _get_estado_civil(self, edad: int) -> str:
        """Determina estado civil basado en edad."""
        for (min_age, max_age), probs in ESTADO_CIVIL_POR_EDAD.items():
            if min_age <= edad <= max_age:
                return np.random.choice(list(probs.keys()), p=list(probs.values()))
        return 'soltero'
    
    def _generate_income(self, ccaa: str, categoria: str, edad: int) -> float:
        """
        Genera ingreso mensual basado en CCAA, categoría laboral y edad.
        Fuente: INE EES + ECV 2024
        """
        base = SALARIO_MEDIO_CCAA.get(ccaa, 2200)
        
        # Ajuste por categoría laboral
        mult_categoria = {
            'funcionario': 1.15,
            'empleado_privado': 1.0,
            'autonomo': 0.95,
            'jubilado': 0.65,
            'desempleado': 0.30,
            'estudiante': 0.15
        }
        
        # Ajuste por edad (curva salarial)
        if edad < 25:
            mult_edad = 0.65
        elif edad < 35:
            mult_edad = 0.85
        elif edad < 45:
            mult_edad = 1.0
        elif edad < 55:
            mult_edad = 1.10
        elif edad < 65:
            mult_edad = 1.05
        else:
            mult_edad = 0.70
        
        # Aplicar multiplicadores
        ingreso = base * mult_categoria.get(categoria, 1.0) * mult_edad
        ingreso *= self.config['multiplicador_ingreso']
        
        # Añadir variabilidad (log-normal para simular distribución real)
        ingreso *= np.random.lognormal(0, 0.3)
        
        return max(450, ingreso)  # SMI como mínimo
    
    def _generate_customer(self, customer_id: int) -> Dict:
        """Genera un cliente completo con todos los campos v4."""
        
        # === DEMOGRAFÍA (Basado en INE) ===
        ccaa = np.random.choice(self.ccaa_names, p=self.ccaa_probs)
        edad = int(np.random.choice(list(range(18, 91)), 
                   p=self._get_age_probs()))
        birth_date = datetime.now() - timedelta(days=edad*365 + np.random.randint(0, 365))
        estado_civil = self._get_estado_civil(edad)
        categoria_laboral = np.random.choice(self.cat_lab_names, p=self.cat_lab_probs)
        
        # Zona postal basada en CCAA y nivel socioeconómico
        tasa_arope = TASA_AROPE_CCAA.get(ccaa, 0.26)
        if np.random.random() > tasa_arope:
            zona_postal = np.random.choice(['A', 'B'], p=[0.4, 0.6])
        else:
            zona_postal = np.random.choice(['C', 'D'], p=[0.6, 0.4])
        
        # === INGRESOS Y GASTOS (Basado en ECV/EPF 2024) ===
        ingreso_medio_mensual = self._generate_income(ccaa, categoria_laboral, edad)
        ingreso_std = ingreso_medio_mensual * np.random.uniform(0.1, 0.3)
        
        # Gasto basado en EPF por CCAA
        gasto_base_anual = GASTO_MEDIO_CCAA.get(ccaa, 13000)
        gasto_medio_mensual = (gasto_base_anual / 12) * np.random.lognormal(0, 0.25)
        gasto_medio_mensual = min(gasto_medio_mensual, ingreso_medio_mensual * 1.2)
        gasto_std = gasto_medio_mensual * np.random.uniform(0.15, 0.35)
        
        # Ahorro
        ahorro_medio_mensual = ingreso_medio_mensual - gasto_medio_mensual
        ahorro_medio_mensual *= self.config['multiplicador_ahorro']
        meses_ahorro_positivo = np.random.binomial(12, max(0, min(1, 0.5 + ahorro_medio_mensual/ingreso_medio_mensual)))
        
        # === CUENTAS BANCARIAS ===
        n_cuentas = np.random.choice([1, 2, 3, 4], p=[0.35, 0.40, 0.18, 0.07])
        n_cuentas_corrientes = min(n_cuentas, np.random.choice([1, 2, 3], p=[0.60, 0.32, 0.08]))
        n_depositos_plazo = n_cuentas - n_cuentas_corrientes
        
        # Saldo basado en EFF 2022
        if categoria_laboral == 'desempleado':
            saldo_mult = 0.3
        elif categoria_laboral == 'jubilado':
            saldo_mult = 1.5
        else:
            saldo_mult = 1.0
        
        saldo_total = max(0, np.random.lognormal(
            np.log(PATRIMONIO_EFF['mediana_activos_financieros'] * saldo_mult / 12),
            0.8
        ))
        saldo_depositos = saldo_total * n_depositos_plazo / max(n_cuentas, 1) if n_depositos_plazo > 0 else 0
        
        tiene_linea_credito = np.random.random() < 0.15
        
        # === TARJETAS (Basado en BCE/PwC 2024) ===
        tiene_tarjeta_credito = np.random.random() < USO_DIGITAL['tarjeta_credito']
        n_tarjetas = 1  # Al menos débito
        if tiene_tarjeta_credito:
            n_tarjetas += np.random.choice([1, 2, 3], p=[0.65, 0.28, 0.07])
        
        # Límite de crédito basado en ingresos
        if tiene_tarjeta_credito:
            limite_credito_total = ingreso_medio_mensual * np.random.uniform(1.5, 4.0)
            credito_dispuesto = limite_credito_total * np.random.beta(2, 5)
            ratio_utilizacion_credito = credito_dispuesto / limite_credito_total
        else:
            limite_credito_total = 0
            credito_dispuesto = 0
            ratio_utilizacion_credito = 0
        
        # === INVERSIONES (Basado en EFF 2022) ===
        # Probabilidad de inversión aumenta con edad e ingresos
        prob_inversion = 0.15 + (edad / 200) + (ingreso_medio_mensual / 20000)
        prob_inversion = min(0.60, prob_inversion)
        tiene_inversiones = np.random.random() < prob_inversion
        
        if tiene_inversiones:
            valor_cartera = np.random.lognormal(
                np.log(PATRIMONIO_EFF['mediana_activos_financieros']),
                1.0
            )
            n_fondos = np.random.choice([1, 2, 3, 4, 5], p=[0.35, 0.30, 0.20, 0.10, 0.05])
            rentabilidad_cartera = np.random.normal(0.05, 0.12)
            aportaciones_ultimo_año = valor_cartera * np.random.uniform(0, 0.15)
        else:
            valor_cartera = 0
            n_fondos = 0
            rentabilidad_cartera = 0
            aportaciones_ultimo_año = 0
        
        # Plan de pensiones (más probable con edad)
        prob_pension = 0.05 + (max(0, edad - 30) / 100)
        tiene_plan_pensiones = np.random.random() < min(0.35, prob_pension)
        
        # === PRÉSTAMOS (Basado en EFF 2022) ===
        # Probabilidad de hipoteca por edad
        tenencia = VIVIENDA_POR_EDAD.get(
            next((k for k in VIVIENDA_POR_EDAD.keys() if k[0] <= edad <= k[1]), (35, 44)),
            {'propietario': 0.6}
        )
        tiene_hipoteca = (np.random.random() < tenencia['propietario'] * 0.6) and (edad < 70)
        tiene_prestamo_consumo = np.random.random() < 0.20
        tiene_prestamo = tiene_hipoteca or tiene_prestamo_consumo
        
        if tiene_prestamo:
            if tiene_hipoteca:
                tipo_prestamo = 'hipotecario'
                capital_original = np.random.lognormal(np.log(150000), 0.5)
                años_total = np.random.choice([15, 20, 25, 30], p=[0.15, 0.30, 0.35, 0.20])
                tipo_interes = np.random.uniform(0.015, 0.045)
            else:
                tipo_prestamo = 'consumo'
                capital_original = np.random.lognormal(np.log(8000), 0.6)
                años_total = np.random.choice([2, 3, 5, 7], p=[0.20, 0.35, 0.30, 0.15])
                tipo_interes = np.random.uniform(0.05, 0.12)
            
            porcentaje_amortizado = np.random.uniform(0.1, 0.8)
            deuda_pendiente = capital_original * (1 - porcentaje_amortizado)
            años_restantes = int(años_total * (1 - porcentaje_amortizado))
            
            # Cuota mensual (aproximación)
            r = tipo_interes / 12
            n = años_restantes * 12
            if n > 0 and r > 0:
                cuota_mensual = deuda_pendiente * (r * (1+r)**n) / ((1+r)**n - 1)
            else:
                cuota_mensual = deuda_pendiente / max(1, n)
        else:
            tipo_prestamo = None
            capital_original = 0
            tipo_interes = 0
            porcentaje_amortizado = 0
            deuda_pendiente = 0
            años_restantes = 0
            cuota_mensual = 0
        
        # === SEGUROS ===
        tiene_seguro = np.random.random() < 0.55
        if tiene_seguro:
            suma_asegurada = np.random.lognormal(np.log(50000), 0.7)
        else:
            suma_asegurada = 0
        
        # === RECIBOS/DOMICILIACIONES ===
        n_domiciliaciones = np.random.poisson(5) + 1
        importe_total_domiciliaciones = n_domiciliaciones * np.random.uniform(30, 150)
        
        # Recibos rechazados (muy correlacionado con riesgo)
        if categoria_laboral == 'desempleado':
            prob_rechazos = 0.25
        elif ahorro_medio_mensual < 0:
            prob_rechazos = 0.15
        else:
            prob_rechazos = 0.03
        tiene_recibos_rechazados = np.random.random() < prob_rechazos
        
        # === PERFIL DE RIESGO ===
        perfiles = self.config['perfiles']
        perfil_probs = [p['proporcion'] for p in perfiles.values()]
        perfil_real = np.random.choice(list(perfiles.keys()), p=perfil_probs)
        
        # === CÁLCULO DE DEFAULT (14 factores calibrados con literatura) ===
        # Fuentes: Costa e Silva et al. (2020) PMC9041570, NBER w26165, Fed Reserve
        # Metodología: Odds Ratios convertidos a multiplicadores
        
        prob_default = perfiles[perfil_real]['prob_default_base']
        
        # Factor 1: Meses ahorro positivo < 3 (proxy de payment history)
        # Fuente: FICO - payment history explica 35% del score
        # OR estimado: 1.8 para historial negativo
        if meses_ahorro_positivo < 3:
            prob_default *= 1.8
        elif meses_ahorro_positivo >= 9:
            prob_default *= 0.7  # Buen historial reduce riesgo
        
        # Factor 2: Sin inversiones (proxy de financial assets)
        # Fuente: EFF 2022 - activos financieros correlacionan con estabilidad
        # OR estimado: 1.4
        if not tiene_inversiones:
            prob_default *= 1.4
        
        # Factor 3: Con préstamo activo
        # Fuente: Costa e Silva (2020) - Term OR=1.044 por año
        # Ajustamos por tener deuda activa
        if tiene_prestamo:
            prob_default *= 1.15
        
        # Factor 4: Ratio deuda/ingreso (DTI)
        # Fuente: Kim et al. (2018) - DTI tiene "profound effect"
        # Fed Reserve: DTI >40% señal de estrés financiero
        ratio_deuda = cuota_mensual / ingreso_medio_mensual if ingreso_medio_mensual > 0 else 0
        if ratio_deuda > 0.50:
            prob_default *= 2.0  # Alto riesgo
        elif ratio_deuda > 0.40:
            prob_default *= 1.5
        elif ratio_deuda > 0.30:
            prob_default *= 1.2
        
        # Factor 5: Recibos rechazados (delinquency history)
        # Fuente: NBER w26165 - delinquencies explican 25-30% del score
        # OR muy alto para historial de impagos previos
        if tiene_recibos_rechazados:
            prob_default *= 3.0  # Aumentado: muy predictivo
        
        # Factor 6: Ratio utilización crédito
        # Fuente: Fed Reserve, FICO - credit utilization 30% del score
        # >80% indica estrés financiero severo
        if ratio_utilizacion_credito > 0.80:
            prob_default *= 1.8
        elif ratio_utilizacion_credito > 0.50:
            prob_default *= 1.3
        elif ratio_utilizacion_credito < 0.30 and tiene_tarjeta_credito:
            prob_default *= 0.85  # Buen uso reduce riesgo
        
        # Factor 7: Plan pensiones (estabilidad financiera)
        # Fuente: EFF 2022 - correlación con planificación a largo plazo
        if tiene_plan_pensiones:
            prob_default *= 0.70
        
        # Factor 8: Depósito a plazo (liquidez + estabilidad)
        # Fuente: EFF 2022 - depósitos = 52% activos financieros
        if n_depositos_plazo > 0:
            prob_default *= 0.80
        
        # Factor 9: Salario domiciliado (proxy de Salary en Costa e Silva)
        # Fuente: Costa e Silva (2020) - OR=0.438 para salary en mismo banco
        # Interpretación: empleo estable con nómina domiciliada
        if categoria_laboral in ['funcionario', 'empleado_privado']:
            prob_default *= 0.75  # OR~0.75 estimado
        
        # Factor 10: Desempleado
        # Fuente: EPA 2024, literatura general
        # OR alto para desempleo
        if categoria_laboral == 'desempleado':
            prob_default *= 2.2
        
        # Factor 11: Tramo fiscal / zona socioeconómica
        # Fuente: Costa e Silva (2020) - Tax Echelon 1 vs otros OR<0.10
        # Zona A/B = mayor renta
        if zona_postal in ['A', 'B']:
            prob_default *= 0.85
        elif zona_postal == 'D':
            prob_default *= 1.25
        
        # Factor 12: Edad + hipoteca (estabilidad)
        # Fuente: Costa e Silva (2020) - Age OR=1.037
        # Pero hipoteca en >45 = patrimonio acumulado
        if edad > 45 and tipo_prestamo == 'hipotecario':
            prob_default *= 0.80
        elif edad < 30:
            prob_default *= 1.15  # Jóvenes = menos historial
        
        # Factor 13: Saldo bajo vs ingresos (buffer financiero)
        # Fuente: EFF 2022 - liquidez como colchón
        if saldo_total < ingreso_medio_mensual * 0.5:
            prob_default *= 1.5  # Sin buffer
        elif saldo_total > ingreso_medio_mensual * 3:
            prob_default *= 0.75  # Buen colchón
        
        # Factor 14: Tasa AROPE regional
        # Fuente: INE ECV 2024 - desigualdad territorial
        tasa_arope_local = TASA_AROPE_CCAA.get(ccaa, 0.26)
        if tasa_arope_local > 0.32:
            prob_default *= 1.20
        elif tasa_arope_local < 0.20:
            prob_default *= 0.90
        
        # Limitar probabilidad final
        prob_default = min(0.95, max(0.005, prob_default))
        default_12m = int(np.random.random() < prob_default)
        
        return {
            'customer_id': customer_id,
            'perfil_real': perfil_real,
            # Demografía
            'edad': edad,
            'birth_date': birth_date.strftime('%Y-%m-%d'),
            'estado_civil': estado_civil,
            'categoria_laboral': categoria_laboral,
            'ccaa': ccaa,
            'zona_postal': zona_postal,
            # Ingresos/Gastos
            'ingreso_medio_mensual': round(ingreso_medio_mensual, 2),
            'ingreso_std': round(ingreso_std, 2),
            'gasto_medio_mensual': round(gasto_medio_mensual, 2),
            'gasto_std': round(gasto_std, 2),
            'ahorro_medio_mensual': round(ahorro_medio_mensual, 2),
            'meses_ahorro_positivo': meses_ahorro_positivo,
            # Cuentas
            'n_cuentas': n_cuentas,
            'n_cuentas_corrientes': n_cuentas_corrientes,
            'n_depositos_plazo': n_depositos_plazo,
            'saldo_total': round(saldo_total, 2),
            'saldo_depositos': round(saldo_depositos, 2),
            'tiene_linea_credito': int(tiene_linea_credito),
            # Tarjetas
            'n_tarjetas': n_tarjetas,
            'tiene_tarjeta_credito': int(tiene_tarjeta_credito),
            'limite_credito_total': round(limite_credito_total, 2),
            'credito_dispuesto': round(credito_dispuesto, 2),
            'ratio_utilizacion_credito': round(ratio_utilizacion_credito, 4),
            # Inversiones
            'tiene_inversiones': int(tiene_inversiones),
            'valor_cartera': round(valor_cartera, 2),
            'n_fondos': n_fondos,
            'tiene_plan_pensiones': int(tiene_plan_pensiones),
            'rentabilidad_cartera': round(rentabilidad_cartera, 4),
            'aportaciones_ultimo_año': round(aportaciones_ultimo_año, 2),
            # Préstamos
            'tiene_prestamo': int(tiene_prestamo),
            'tipo_prestamo': tipo_prestamo,
            'capital_original': round(capital_original, 2),
            'tipo_interes': round(tipo_interes, 4),
            'porcentaje_amortizado': round(porcentaje_amortizado, 4),
            'deuda_pendiente': round(deuda_pendiente, 2),
            'años_restantes': años_restantes,
            'cuota_mensual': round(cuota_mensual, 2),
            # Seguros
            'tiene_seguro': int(tiene_seguro),
            'suma_asegurada': round(suma_asegurada, 2),
            # Recibos
            'n_domiciliaciones': n_domiciliaciones,
            'importe_total_domiciliaciones': round(importe_total_domiciliaciones, 2),
            'tiene_recibos_rechazados': int(tiene_recibos_rechazados),
            # Target
            'default_12m': default_12m
        }
    
    def _get_age_probs(self) -> List[float]:
        """Genera probabilidades para cada edad 18-90."""
        probs = []
        for age in range(18, 91):
            for (min_age, max_age), prob in DISTRIBUCION_EDAD.items():
                if min_age <= age <= max_age:
                    probs.append(prob / (max_age - min_age + 1))
                    break
        total = sum(probs)
        return [p/total for p in probs]
    
    def generate(self, n_customers: int, start_id: int = 1) -> pd.DataFrame:
        """
        Genera dataset de clientes.
        
        Args:
            n_customers: Número de clientes a generar
            start_id: ID inicial
            
        Returns:
            DataFrame con clientes generados
        """
        customers = []
        for i in range(n_customers):
            customer = self._generate_customer(start_id + i)
            customers.append(customer)
            
            if (i + 1) % 10000 == 0:
                print(f"  Generados {i + 1:,}/{n_customers:,} clientes...")
        
        return pd.DataFrame(customers)


# =============================================================================
# FUNCIONES DE GENERACIÓN POR LOTES
# =============================================================================

def generate_batch(args):
    """Genera un lote de clientes (para multiprocessing)."""
    scenario, batch_size, start_id, seed = args
    gen = WealthReaderSyntheticGeneratorV6(scenario=scenario, seed=seed)
    return gen.generate(batch_size, start_id)


def generate_in_batches(
    scenario: str,
    total_customers: int,
    batch_size: int = 50000,
    output_dir: str = '.',
    suffix: str = '',
    seed: int = 42,
    n_workers: int = None
) -> pd.DataFrame:
    """
    Genera dataset en lotes para manejar memoria eficientemente.
    
    Args:
        scenario: 'normal', 'crisis', 'boom'
        total_customers: Total de clientes
        batch_size: Tamaño de cada lote
        output_dir: Directorio de salida
        n_workers: Número de workers (default: CPU cores)
    
    Returns:
        DataFrame combinado
    """
    if n_workers is None:
        n_workers = max(1, cpu_count() - 1)
    
    n_batches = (total_customers + batch_size - 1) // batch_size
    print(f"\n{'='*60}")
    print(f"GENERADOR WEALTHREADER v6 - Estadísticas Oficiales España")
    print(f"{'='*60}")
    print(f"Escenario: {scenario} ({ESCENARIOS[scenario]['nombre']})")
    print(f"Clientes: {total_customers:,}")
    print(f"Lotes: {n_batches} × {batch_size:,}")
    print(f"Workers: {n_workers}")
    print(f"{'='*60}\n")
    
    # Preparar argumentos para cada lote
    batch_args = []
    for i in range(n_batches):
        start_id = i * batch_size + 1
        actual_size = min(batch_size, total_customers - i * batch_size)
        batch_seed = seed + i * 100
        batch_args.append((scenario, actual_size, start_id, batch_seed))
    
    # Generar en paralelo
    all_dfs = []
    with Pool(n_workers) as pool:
        for i, df in enumerate(pool.imap(generate_batch, batch_args)):
            all_dfs.append(df)
            print(f"✓ Lote {i+1}/{n_batches} completado ({len(df):,} clientes)")
            gc.collect()
    
    # Combinar
    print("\nCombinando lotes...")
    df_final = pd.concat(all_dfs, ignore_index=True)
    
    # Estadísticas
    print(f"\n{'='*60}")
    print("RESUMEN ESTADÍSTICO")
    print(f"{'='*60}")
    print(f"Total clientes: {len(df_final):,}")
    print(f"Tasa default: {df_final['default_12m'].mean()*100:.2f}%")
    print(f"Ingreso medio: {df_final['ingreso_medio_mensual'].mean():,.0f}€")
    print(f"Saldo medio: {df_final['saldo_total'].mean():,.0f}€")
    print(f"\nDistribución por CCAA (top 5):")
    print(df_final['ccaa'].value_counts().head())
    print(f"\nDistribución por categoría laboral:")
    print(df_final['categoria_laboral'].value_counts())
    
    # Guardar (formato compatible con generate_1M.sh)
    # Si suffix incluye scenario (ej: "normal_1"), usar solo suffix
    # Si no, usar scenario_suffix
    if suffix:
        output_file = f"{output_dir}/wealthreader_synthetic_customers_{suffix}.csv"
    else:
        output_file = f"{output_dir}/wealthreader_synthetic_customers_{scenario}.csv"
    df_final.to_csv(output_file, index=False)
    print(f"\n✓ Guardado: {output_file}")
    
    return df_final


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generador WealthReader v6 - Datos sintéticos basados en INE/BdE',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generator_wealthreader_v6.py --scenario normal --customers 100000
  python generator_wealthreader_v6.py --scenario crisis --customers 500000 --batch-size 50000
  python generator_wealthreader_v6.py --scenario all --customers 350000

Fuentes de datos:
  - INE: Encuesta de Condiciones de Vida 2024
  - INE: Encuesta de Presupuestos Familiares 2024
  - INE: Encuesta de Estructura Salarial
  - Banco de España: Encuesta Financiera de las Familias 2022
        """
    )
    
    parser.add_argument('--scenario', '-s', type=str, default='normal',
                        choices=['normal', 'crisis', 'boom', 'all'],
                        help='Escenario económico (default: normal)')
    parser.add_argument('--customers', '-n', type=int, default=50000,
                        help='Número de clientes (default: 50000)')
    parser.add_argument('--batch-size', type=int, default=50000,
                        help='Tamaño de lote (default: 50000)')
    parser.add_argument('--output-dir', '-o', type=str, default='.',
                        help='Directorio de salida (default: .)')
    parser.add_argument('--suffix', '-x', type=str, default='',
                        help='Sufijo para nombres de archivo')
    parser.add_argument('--seed', type=int, default=42,
                        help='Semilla aleatoria (default: 42)')
    parser.add_argument('--workers', type=int, default=None,
                        help='Número de workers (default: auto)')
    
    args = parser.parse_args()
    
    if args.scenario == 'all':
        # Generar los 3 escenarios
        all_dfs = []
        for scenario in ['normal', 'crisis', 'boom']:
            df = generate_in_batches(
                scenario=scenario,
                total_customers=args.customers,
                batch_size=args.batch_size,
                output_dir=args.output_dir,
                suffix=args.suffix,
                seed=args.seed,
                n_workers=args.workers
            )
            df['escenario'] = scenario
            all_dfs.append(df)
        
        # Combinar
        df_combined = pd.concat(all_dfs, ignore_index=True)
        df_combined['customer_id'] = range(1, len(df_combined) + 1)
        
        suffix_str = f"_{args.suffix}" if args.suffix else ""
        output_file = f"{args.output_dir}/wealthreader_v6_combined_{args.customers * 3}{suffix_str}.csv"
        df_combined.to_csv(output_file, index=False)
        print(f"\n✓ Dataset combinado: {output_file}")
        print(f"  Total: {len(df_combined):,} clientes")
        print(f"  Default rate global: {df_combined['default_12m'].mean()*100:.2f}%")
    else:
        generate_in_batches(
            scenario=args.scenario,
            total_customers=args.customers,
            batch_size=args.batch_size,
            output_dir=args.output_dir,
            suffix=args.suffix,
            seed=args.seed,
            n_workers=args.workers
        )


if __name__ == '__main__':
    main()