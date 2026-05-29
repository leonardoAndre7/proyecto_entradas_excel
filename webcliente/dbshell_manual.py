import sqlite3
import os

# Ruta a tu base de datos de Django
BASE_DIR = r"C:\Documentos\Proyecto_entradas_excel\webcliente"
db_path = os.path.join(BASE_DIR, "db.sqlite3")

# Conectar a la base de datos
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Conectado a la base de datos. Puedes ejecutar consultas SQL ahora.")

# Ejemplo: ver todas las tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tablas existentes:", tables)

# Mantener la sesión abierta (opcional)
while True:
    sql = input("SQL> ")
    if sql.lower() in ["exit", "quit"]:
        break
    try:
        cursor.execute(sql)
        if sql.strip().lower().startswith("select"):
            print(cursor.fetchall())
        else:
            conn.commit()
            print("Consulta ejecutada.")
    except Exception as e:
        print("Error:", e)

conn.close()
print("Conexión cerrada.")
