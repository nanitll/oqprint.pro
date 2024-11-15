import sqlite3
from datetime import datetime

# Путь к базе данных
DB_HISTORY_PATH = 'data/history.db'

# Функция для подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect(DB_HISTORY_PATH)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к строкам как к словарям
    return conn

# Функция для создания таблицы, если она еще не существует
def create_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            order_number TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Функция для сохранения истории в базу данных
def save_history(order_number, timestamp):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Просто добавляем запись для данного номера заказа
    c.execute('INSERT INTO history (order_number, timestamp) VALUES (?, ?)', (order_number, timestamp))

    conn.commit()
    conn.close()

# Функция для получения истории по номеру заказа
def load_history(order_number):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT timestamp FROM history WHERE order_number = ?', (order_number,))
    history = c.fetchall()
    conn.close()
    return [entry['timestamp'] for entry in history]  # Возвращаем список таймстампов
