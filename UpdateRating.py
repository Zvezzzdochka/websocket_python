import asyncio
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import sys
import secrets
import datetime
import base64
import time
import schedule

def update():
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    await connection.execute('''UPDATE tagme.rating
                SET place = (
                    SELECT COUNT(*) + 1
                    FROM tagme.rating AS r2
                    WHERE r2.user_score > rating.user_score
                )''')
    print("Функция выполнена!")

# Запланировать выполнение функции один раз в 24 часа
schedule.every().day.at("00:00").do(update)

while True:
    schedule.run_pending()
    time.sleep(1)