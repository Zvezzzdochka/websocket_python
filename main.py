import asyncio
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import sys
import secrets
import datetime
status = True
message = ''
class TokenManager:

    def __init__(self):
        self.dictionary_token = {}
    async def generate_token(self): # Генерация токена
        return secrets.token_urlsafe(16)

    async def write_dictionary(self, user_id, token): # Запись токена
        self.dictionary_token[user_id] = token
        self.dictionary_token[token] = user_id

    async def read_dictionary(self, user_id): # Проверка наличия id (или токена)
        return user_id in self.dictionary_token

    async def get_user_id(self, token):
        return self.dictionary_token[token]

    async def pop_dictionary(self, user_id):
        self.dictionary_token.pop(self.dictionary_token[user_id])

tokenManager = TokenManager()
async def register_user(username, password): # Регистрация пользователя
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        result = await connection.fetchval('''SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE' ELSE 'FALSE' END AS result''', username)
        if result == 'FALSE':
            token = await tokenManager.generate_token()
            id_string = await connection.fetchval('INSERT INTO tagme."user" (nickname, password) VALUES($1, $2) returning id', username, password)
            id = int(id_string)
            await tokenManager.write_dictionary(id, token)
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
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        result = await connection.fetchval('''SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1 AND password = $2) THEN (select id from tagme."user" WHERE nickname = $1 AND password = $2)::varchar(10) ELSE 'FALSE' END AS result''', username, password)
        if result == 'FALSE':
            status = False
            message = 'failed'
        else:
            token = await tokenManager.generate_token()
            result_id = int(result)
            if await tokenManager.read_dictionary(result_id):
                await tokenManager.pop_dictionary(result_id)
            await tokenManager.write_dictionary(result_id, token)
            status = True
            message = token
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def login_token(token): #Вход по токену
    global status, message, tokenManager
    if await tokenManager.read_dictionary(token):
        status = True
        message = 'success'
    else:
        status = False
        message = 'error'

async def send_location(token, latitude, longitude, accuracy, speed, timestamp): #Обновление location пользователя
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('INSERT INTO tagme.location (user_id, latitude, longitude, accuracy, speed, timestamp) VALUES($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id) DO UPDATE SET latitude = $2, longitude = $3, accuracy = $4, speed = $5, timestamp = $6', user_id, latitude, longitude, accuracy, speed, timestamp)
            status = True
            message = 'success'
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def get_locations(token): # получение локации друзей
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT "user".id, nickname, latitude, longitude, accuracy, speed, timestamp FROM tagme.location
    LEFT JOIN tagme.user_link ON tagme.location.user_id = tagme.user_link.user2_id AND tagme.user_link.user1_id = $1
    LEFT JOIN tagme."user" ON tagme.location.user_id = "user".id
WHERE tagme.user_link.relation = \'friend\'''', user_id)
            result = {"result": [{"user_id": record["id"], "nickname": record["nickname"],
                                  "latitude": record["latitude"],
                                  "longitude": record["longitude"],
                                  "accuracy": record["accuracy"],
                                  "speed": record["speed"],
                                  "timestamp": record["timestamp"].isoformat()} for record in records]}
            status = True
            message = json.dumps((result))
        else:
            status = False
            message = 'no location'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def add_friend(token, nickname): #Отправка заявки в друзья
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            result = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', nickname)

            resultOnBlocked = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'blocked') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)

            resultOnFriend = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'friend') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if (result == 'TRUE'):
                if (resultOnBlocked == 'FALSE'):
                    if (resultOnFriend == 'FALSE'):
                        await connection.execute('''DO
                            $do$
                                BEGIN
                                    IF NOT EXISTS (SELECT user1_id, user2_id FROM tagme.user_link WHERE user1_id = $1 AND user2_id = (SELECT id from tagme."user" where nickname = $2)) THEN
                                        INSERT INTO tagme.user_link (user1_id, user2_id,relation)
                                        VALUES ($1,(SELECT id from tagme."user" where nickname = $2), 'outgoing'),
                                               ((SELECT id from tagme."user" where nickname = $2), $1, 'incoming');
                                    ELSE
                                        UPDATE tagme.user_link set relation = 'outgoing' where user1_id = $1 and user2_id = (SELECT id from tagme."user" where nickname = $2);
                                        UPDATE tagme.user_link set relation = 'incoming' where user1_id = (SELECT id from tagme."user" where nickname = $2) and user2_id = $1;
                                    END IF;
                                END
                            $do$''', user_id, nickname)
                        status = True
                        message = 'success'
                    else:
                        status = False
                        message = 'user is already a friend'
                else:
                    status = False
                    message = 'user was blocked by this user'
            else:
                status = False
                message = 'no user'
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

# async def loading_pfp_friends(token):   #Загрузка картинка друзей
#     global status, message, tokenManager
#     connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
#                                        host='141.8.193.201')
#     try:
#         if await tokenManager.read_dictionary(token):
#             user_id = await tokenManager.get_user_id(token)
#             result = await connection.fetchval('''SELECT "user".id, nickname, picture_id, picture  FROM tagme.user_link
#       INNER JOIN tagme."user" ON tagme.user_link.user2_id = tagme."user".id AND tagme.user_link.user1_id = $1
#       LEFT JOIN tagme.picture ON tagme.picture.id = picture_id
# WHERE tagme.user_link.relation = \'friend\'''', user_id)
#             status = True
#             message = result
#         else:
#             status = False
#             message = 'failed loading chats'
#     except:
#         message = str(sys.exc_info()[1])
#         status = False
#     finally:
#         await connection.close()
async def cancel_outgoing_request(token, user2_id): # Отменить исходящую заявку
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
               set relation = 'default'
               where (relation = 'incoming' OR relation = 'outgoing') AND
                   ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))''', user_id, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def accept_friend(token, user2_id): # принятие в друзья -- переделано: nickname - это user_id второго польз.
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
   set relation = 'friend', date_linked = $3
   where (relation = 'incoming' OR relation = 'outgoing') AND
       ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))''', user_id, user2_id, datetime.datetime.now())
            await connection.execute('''INSERT INTO tagme.conversation (user1_id, user2_id)
   SELECT
       $1, $2
   WHERE NOT EXISTS (
       SELECT 1 FROM tagme.conversation WHERE ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1)))''', user_id, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

#Вообще эту функцию можно использовать еще как удаление из друзей!
async def reject_friend(token, user2_id): # Отклонение запроса в друзья -- переделано: nickname - это user_id второго польз.
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link 
SET relation = 'default'
WHERE (user1_id = $1 and user2_id = $2) or (user1_id = $2 and user2_id = $1)''', user_id, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def loading_friend_requests(token): # Загрузка списка входящих и исходящих заявок в друзья
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT "user".id, nickname, relation FROM tagme."user"
    LEFT JOIN tagme.user_link ON tagme."user".id = tagme.user_link.user2_id AND tagme.user_link.user1_id = $1
WHERE tagme.user_link.relation = 'incoming' OR tagme.user_link.relation = \'outgoing\'''', user_id)
            result = {"result": [{"user_id": record["id"], "nickname": record["nickname"],
                                  "relation": record["relation"]} for record in records]}
            status = True
            message = result
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def loading_chats(token):    #Загрузка чатов
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            result = await connection.fetchval('SELECT id FROM tagme.conversation where (user1_id = $1)', user_id)
            status = True
            message = result
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def loading_messages(token, last_msg_id):    #Загрузка сообщений в чате
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            result = await connection.fetchval('select id, author_id ,text, timestamp from tagme.message where (conversation_id = $1 AND id < $2) LIMIT 20', user_id, last_msg_id)
            status = True
            message = result
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def Websocket(websocket, path):
    global status, message, tokenManager
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

            case "validate token":
                token = user_data.get('token')
                await login_token(token)

            case "send location":
                token = user_data.get('token')
                latitude = float(user_data.get('latitude'))
                longitude = float(user_data.get('longitude'))
                accuracy = float(user_data.get('accuracy'))
                speed = float(user_data.get('speed'))
                timestamp = datetime.datetime.now()
                await send_location(token, latitude, longitude, accuracy, speed, timestamp)
            case "get locations":
                token = user_data.get('token')
                await get_locations(token)
            case "add friend":
                token = user_data.get('token')
                nickname = user_data.get('nickname')
                await add_friend(token, nickname)
            case "accept friend":
                token = user_data.get('token')
                nickname = user_data.get('nickname')
                await accept_friend(token, nickname)
            case "reject friend":
                token = user_data.get('token')
                nickname = user_data.get('nickname')
                await reject_friend(token, nickname)
            case "loading chat":
                token = user_data.get('token')
                await loading_chats(token)
            case _:
                status = False
                message = "action mismatch"

        response = {'action': action, 'status': 'success' if status else 'error', 'message': message}
        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(Websocket, '141.8.193.201', 8765)  # Запуск WebSocket сервера на localhost и порту 8765

asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера