import pandas as pd 
from sqlalchemy import create_engine

# 🔹 Conexión a PostgreSQL
engine = create_engine('postgresql+psycopg2://inventario_db_gg37_user:tr1cmIiptMke93DgahbXMJ8BpAOdp133@dpg-cv8rv652ng1s73bd3ee0-a.oregon-postgres.render.com/inventario_db_gg37')

# 🔹 Cargar el archivo Excel (ajustando el header a la primera fila)
df = pd.read_excel("inventario.xlsx", header=0)

# 🔹 Ajustar los nombres de las columnas para que coincidan con la base de datos
df.columns = (df.columns
              .str.strip()
              .str.lower()
              .str.replace(' ', '_')
              .str.replace('á', 'a')
              .str.replace('é', 'e')
              .str.replace('í', 'i')
              .str.replace('ó', 'o')
              .str.replace('ú', 'u'))

# 🔹 Renombrar las columnas para coincidir con la base de datos
df = df.rename(columns={
    'cantidad': 'stock_disponible',
    'unidad': 'unidades'  
})

# 🔹 Filtrar solo las columnas necesarias según la estructura actual de la BD
expected_columns = {'producto_nombre', 'stock_disponible', 'unidades', 'stock_critico', 'categoria'}
df = df[list(expected_columns.intersection(df.columns))]

# 🔹 Agregar las columnas que podrían faltar en el archivo Excel con valores por defecto
if 'stock_critico' not in df.columns:
    df['stock_critico'] = 0  # Valor por defecto

if 'categoria' not in df.columns:
    df['categoria'] = 'Sin categoría'  # Valor por defecto

# 🔹 Subir los datos a PostgreSQL en la tabla "productos"
df.to_sql('productos', con=engine, if_exists='replace', index=False, method="multi")

print("✅ Inventario importado correctamente a PostgreSQL con las columnas actualizadas")
