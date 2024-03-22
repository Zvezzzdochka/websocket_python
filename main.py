import asyncio
import websockets
import json
import re  # Импорт модуля для работы с регулярными выражениями

registered_users = {}  # Словарь для хранения зарегистрированных пользователей (логин: пароль)


async def register_user(websocket, path):
    while True:
        data = await websocket.recv()  # Получение данных от клиента
        user_data = json.loads(data)  # Преобразование полученных данных из JSON в объект Python

        username = user_data.get('username')  # Получение логина пользователя из запроса
        password = user_data.get('password')  # Получение пароля пользователя из запроса

        if username and password:  # Проверка наличия логина и пароля в запросе
            # Проверка сложности пароля: если пароль < 8 символов, не содержит заглавных букв и цифр
            if len(password) < 8 or not any(char.isupper() for char in password) or not any(
                    char.isdigit() for char in password):
                response = {'status': 'error', 'message': 'Пароль слишком простой'}
            else:
                # Регистрация пользователя, если пароль соответствует требованиям
                registered_users[username] = password
                response = {'status': 'success', 'message': 'Пользователь зарегистрирован успешно'}
        else:
            response = {'status': 'error', 'message': 'Отсутствуют логин и/или пароль в запросе'}

        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(register_user, 'localhost', 10.0.2.2)  # Запуск WebSocket сервера на localhost и порту 8765

asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера