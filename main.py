import asyncio
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import re  # Импорт модуля для работы с регулярными выражениями
import sys
import secrets
status = True
message = ''
dictionary_token = {}
async def generate_token(): # Генерация токена
    return secrets.token_urlsafe(16)
async def register_user(username, password): # Регистрация пользователя
    global status, message
    try:
        connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
        result = await connection.fetchval('SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN \'TRUE\' ELSE \'FALSE\' END AS result', username)
        if result == 'FALSE':
            token = await generate_token()
            id_string = await connection.fetchval('INSERT INTO tagme."user" (nickname, password) VALUES($1, $2) returning id', username, password)
            id = int(id_string)
            dictionary_token[id] = token
            dictionary_token[token] = id
            status = True
            message = token
        else:
            status = False
            message = 'username already exists'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def login_user(username, password): # Вход пользователя
    global status, message
    try:
        connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
        result = await connection.fetchval('SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1 AND password = $2) THEN (select id from tagme."user" WHERE nickname = $1 AND password = $2)::varchar(10) ELSE \'FALSE\' END AS result', username, password)
        if result == 'FALSE':
            status = False
            message = 'failed'
        else:
            token = await generate_token()
            result_id = int(result)
            if (result_id in dictionary_token.keys()):
                dictionary_token.pop(dictionary_token[result_id])
            dictionary_token[result_id] = token
            dictionary_token[token] = result_id
            status = True
            message = token
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def Websocket(websocket, path):
    global status, message
    while True:
        data = await websocket.recv()  # Получение данных от клиента
        user_data = json.loads(data)  # Преобразование полученных данных из JSON в объект Python
        action = user_data.get("action")
        match action:
            case "register":
                username = user_data.get('username')  # Получение логина пользователя из запроса
                password = user_data.get('password')  # Получение пароля пользователя из запроса

                if username and password:  # Проверка наличия логина и пароля в запросе
                    status = True
                    message = 'success'
                    error_list = []
                    # Проверка сложности пароля: если пароль < 8 символов, не содержит заглавных букв и цифр
                    if (len(password) < 8):
                        error_list.append('too short')
                        status = False
                    if (len(username) > 14):
                        error_list.append('login too long')
                        status = False
                    if (len(password) > 19):
                        error_list.append('password too long')
                        status = False
                    if (not any(char.isupper() for char in password)):
                        error_list.append('no capital')
                        status = False
                    if (not any(char.isdigit() for char in password)):
                        error_list.append('no digits')
                        status = False
                    if status:

                        await register_user(username, password)

                    else:
                        message = 'input_error:' + ', '.join(error_list)
                else:
                    message = 'no login or password'
            case "login":
                username = user_data.get('username')
                password = user_data.get('password')
                await login_user(username, password)

            case _:
                message = "action mismatch"
        response = {'status': 'success' if status else 'error', 'message': message}
        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(Websocket, '141.8.193.201', 8765)  # Запуск WebSocket сервера на localhost и порту 8765

asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера