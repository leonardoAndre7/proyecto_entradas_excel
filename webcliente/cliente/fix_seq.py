import sqlite3

# Ruta a tu base de datos
db_path = r"C:/Documentos/Proyecto_entradas_excel/webcliente/cliente/db.sqlite3"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Actualiza la secuencia al máximo id actual
cur.execute("""
UPDATE sqlite_sequence
SET seq = (SELECT MAX(id) FROM cliente_previaparticipantes)
WHERE name='cliente_previaparticipantes';
""")

conn.commit()
conn.close()
print("Secuencia actualizada correctamente.")
