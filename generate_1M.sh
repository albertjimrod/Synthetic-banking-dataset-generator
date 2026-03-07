#!/bin/bash
# generate_data.sh - Genera datos sintéticos en lotes

echo "=========================================="
echo "GENERADOR DE DATOS WEALTHREADER"
echo "=========================================="

# Preguntar cantidad
read -p "¿Cuántas instancias quieres generar? [1000000]: " TOTAL
TOTAL=${TOTAL:-1000000}

# Preguntar directorio
read -p "¿Directorio de salida? [data]: " OUTPUT_DIR
OUTPUT_DIR=${OUTPUT_DIR:-data}

# Configuración
BATCH_SIZE=50000
BATCHES_PER_SCENARIO=$(( ($TOTAL / 3 + $BATCH_SIZE - 1) / $BATCH_SIZE ))

mkdir -p $OUTPUT_DIR

echo ""
echo "Configuración:"
echo "  Total instancias: $TOTAL"
echo "  Por escenario: $(($TOTAL / 3))"
echo "  Tamaño lote: $BATCH_SIZE"
echo "  Lotes por escenario: $BATCHES_PER_SCENARIO"
echo "  Directorio: $OUTPUT_DIR"
echo ""
read -p "¿Continuar? (s/n) [s]: " CONFIRM
CONFIRM=${CONFIRM:-s}

if [[ $CONFIRM != "s" && $CONFIRM != "S" ]]; then
    echo "Cancelado"
    exit 0
fi

echo ""
echo "=========================================="
echo "GENERANDO DATOS"
echo "=========================================="

# Normal
for i in $(seq 1 $BATCHES_PER_SCENARIO); do
    SEED=$((42 + i * 100))
    echo "Normal - Lote $i/$BATCHES_PER_SCENARIO"
    python generator_wealthreader_v6_2.py --scenario normal --customers $BATCH_SIZE --suffix normal_$i --seed $SEED --output $OUTPUT_DIR
done

# Crisis
for i in $(seq 1 $BATCHES_PER_SCENARIO); do
    SEED=$((1000 + i * 100))
    echo "Crisis - Lote $i/$BATCHES_PER_SCENARIO"
    python generator_wealthreader_v6_2.py --scenario crisis --customers $BATCH_SIZE --suffix crisis_$i --seed $SEED --output $OUTPUT_DIR
done

# Boom
for i in $(seq 1 $BATCHES_PER_SCENARIO); do
    SEED=$((2000 + i * 100))
    echo "Boom - Lote $i/$BATCHES_PER_SCENARIO"
    python generator_wealthreader_v6_2.py --scenario boom --customers $BATCH_SIZE --suffix boom_$i --seed $SEED --output $OUTPUT_DIR
done

echo ""
echo "=========================================="
echo "COMBINANDO ARCHIVOS"
echo "=========================================="

python << EOF
import pandas as pd
import glob
import os

output_dir = "$OUTPUT_DIR"
dfs = []
current_id = 1

for scenario in ['normal', 'crisis', 'boom']:
    files = sorted(glob.glob(f"{output_dir}/wealthreader_synthetic_customers_{scenario}_*.csv"))
    for f in files:
        df = pd.read_csv(f)
        df['escenario'] = scenario
        df['customer_id'] = range(current_id, current_id + len(df))
        current_id += len(df)
        dfs.append(df)
        print(f"  {f}: {len(df):,} filas")
        os.remove(f)

df_combined = pd.concat(dfs, ignore_index=True)
df_combined.to_csv(f"{output_dir}/wealthreader_combined.csv", index=False)

print(f"\n✅ Archivo final: {output_dir}/wealthreader_combined.csv")
print(f"   Total filas: {len(df_combined):,}")
print(f"   Default rate: {df_combined['default_12m'].mean()*100:.2f}%")
print(f"   Por escenario:")
print(df_combined.groupby('escenario')['default_12m'].agg(['count', 'mean']))
EOF

echo ""
echo "✅ COMPLETADO"
