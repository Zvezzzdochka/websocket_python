import asyncio
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import re  # Импорт модуля для работы с регулярными выражениями

async def register_user(user_data): # Регистрация пользователя
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        await connection.execute("INSERT INTO users(username, password) VALUES($1, $2)", user_data['username'], user_data['password'])
    finally:
        await connection.close()

async def Websocket(websocket, path):
    while True:
        data = await websocket.recv()  # Получение данных от клиента
        user_data = json.loads(data)  # Преобразование полученных данных из JSON в объект Python
        action = user_data.get("action")
        match action:
            case "register":
                username = user_data.get('username')  # Получение логина пользователя из запроса
                password = user_data.get('password')  # Получение пароля пользователя из запроса

                if username and password:  # Проверка наличия логина и пароля в запросе
                    status = true
                    error_list = []
                    # Проверка сложности пароля: если пароль < 8 символов, не содержит заглавных букв и цифр
                    if (len(password) < 8):
                        error_list.append('too short')
                        status = false
                    if (not any(char.isupper() for char in password)):
                        error_list.append('no capital')
                        status = false
                    if (not any(char.isdigit() for char in password)):
                        error_list.append('no digits')
                        status = false
                    if status:
                        await register_user(user_data)
                        message = "success"
                    else:
                        message = 'input_error:' + ', '.join(error_list)
                else:
                    message = 'no login or password'

        response = {'status': status * 'success' + (not status) * 'error', 'message': message}
        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(register_user, '192.168.56.1', 8080)  # Запуск WebSocket сервера на localhost и порту 8765

asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера