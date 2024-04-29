import asyncio
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import sys
import secrets
import datetime
import base64
status = True
message = ''
class TokenManager:

    def __init__(self):
        self.dictionary_token = {}
        self._lock = asyncio.Lock()
    async def generate_token(self): # Генерация токена
        async with self._lock:
            return secrets.token_urlsafe(16)

    async def write_dictionary(self, user_id, token): # Запись токена
        async with self._lock:
            self.dictionary_token[user_id] = token
            self.dictionary_token[token] = user_id

    async def read_dictionary(self, user_id): # Проверка наличия id (или токена)
        async with self._lock:
            return user_id in self.dictionary_token

    async def get_user_id(self, token):
        async with self._lock:
            return self.dictionary_token[token]

    async def pop_dictionary(self, user_id):
        async with self._lock:
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

async def get_friends(token): # Получение списка друзей
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT "user".id AS user_id, nickname, picture.id AS picture_id FROM tagme."user"
    LEFT JOIN tagme.user_link ON user2_id = "user".id
    LEFT JOIN tagme.picture ON tagme."user".picture_id = tagme.picture.id
WHERE user1_id = $1 AND relation = \'friend\'''', user_id)
            result = {"result": [{"user_id": record["user_id"], "nickname": record["nickname"], "picture_id": record["picture_id"]} for record in records]}
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'invalid token'
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
            message = json.dumps(result)
        else:
            status = False
            message = 'invalid token'
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
            doesExist = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', nickname)
            if doesExist == 'FALSE':
                status = False
                message = 'User doesn\'t exist'
                return

            isYou = await connection.fetchval('''SELECT CASE
           WHEN ((SELECT id FROM tagme."user" WHERE nickname = $2) = $1) THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isYou == 'TRUE':
                status = False
                message = "Are u retarded?"
                return

            isBlocked = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'blocked') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isBlocked == 'TRUE':
                status = False
                message = 'You have been blocked by this user'
                return

            isFriend = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'friend') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isFriend == 'TRUE':
                status = False
                message = 'You are already friends'
                return
            await connection.execute("CALL tagme.add_or_update_user_link($1, $2)", str(user_id), nickname)
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

async def get_picture(token, picture_id):   # Загрузка картинки
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT id, picture FROM tagme.picture WHERE (id = $1)''', picture_id)
            result = {"result": [{"picture_id": record['id'], "picture": base64.b64encode(record["picture"]).decode('utf-8')} for record in records]}
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()

async def get_my_data(token):   # Получение данных пользователя(по токену)
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT id, "user".picture_id FROM tagme."user" WHERE id = $1''', user_id)
            result = {"result": [{"user_id": record["id"], "picture_id": record["picture_id"]} for record in records]}
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
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
async def accept_request(token, user2_id): # принятие в друзья -- переделано: nickname - это user_id второго польз.
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
   set relation = 'friend', date_linked = $3
   where (relation = 'incoming' OR relation = 'outgoing') AND
       ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))''', user_id, user2_id, datetime.date.today())
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
async def deny_request(token, user2_id): # Отклонение запроса в друзья -- переделано: nickname - это user_id второго польз.
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
async def get_friend_requests(token): # Загрузка списка входящих и исходящих заявок в друзья
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT "user".id AS user_id, nickname, picture.id AS picture_id, relation 
                                                FROM tagme."user"
                                                LEFT JOIN tagme.user_link ON tagme."user".id = tagme.user_link.user2_id 
                                                    AND tagme.user_link.user1_id = $1
                                                LEFT JOIN tagme.picture ON tagme."user".picture_id = tagme.picture.id
                                                WHERE tagme.user_link.relation = 'incoming' OR tagme.user_link.relation = 'outgoing' 
                                                ORDER BY nickname ASC''', user_id)
            result = {"result": [{"user_id": record['user_id'], "nickname": record["nickname"],
                                  "picture_id": record['picture_id'], "relation": record["relation"]} for record in
                                 records]}
            status = True
            message = json.dumps((result))
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def get_chats(token):    #Загрузка чатов
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT conversation.id AS conversation_id, "user".id AS user_id, nickname,  picture.id AS profile_picture_id, author_id, text, message.picture_id AS msg_picture_id, read, message.timestamp AS timestamp FROM tagme.conversation
    LEFT JOIN tagme."user" ON "user".id = conversation.user1_id OR "user".id = conversation.user2_id
    LEFT JOIN tagme.picture ON tagme."user".picture_id = tagme.picture.id
    LEFT JOIN tagme.message ON conversation.id = message.conversation_id
WHERE (user1_id = $1 OR user2_id = $1) AND ("user".id != $1) AND (not exists(select * from tagme.message where conversation_id = conversation.id) OR (message.id = (select id from tagme.message where conversation_id = conversation.id order by id desc limit 1)))''', user_id)
            result = {"result": [{"conversation_id": record['conversation_id'], "user_id": record['user_id'],
                                  "author_id": record["author_id"], "nickname": record['nickname'],
                                  "profile_picture_id": record['profile_picture_id'],
                                  "text": record["text"], "msg_picture_id": record["msg_picture_id"],
                                  "read": record["read"], "timestamp": record["timestamp"].isoformat() if record["timestamp"] else None} for record in records]}
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def get_messages(token, conversation_id, last_msg_id):    #Загрузка сообщений в чате
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            if last_msg_id == -1:
                records = await connection.fetch('''SELECT * FROM (
                  SELECT id, conversation_id, author_id, text, picture_id, read, timestamp
                  FROM tagme.message
                  WHERE conversation_id = $1
                    AND id <= (SELECT id FROM tagme.message ORDER BY id DESC LIMIT 1)
                  ORDER BY id DESC
                  LIMIT 20
              ) AS subquery
ORDER BY id ASC''', conversation_id)
                result = {"result": [{"message_id": record["id"], "conversation_id": record["conversation_id"],
                                      "author_id": record["author_id"],
                                      "text": record["text"], "picture_id": record["picture_id"], "read": record["read"],
                                      "timestamp": record["timestamp"].isoformat()} for record in records]}
            else:
                records = await connection.fetch('select id, conversation_id, author_id ,text, picture_id, read, timestamp from tagme.message where (conversation_id = $1 and id <= $2) LIMIT 20',
                                                 conversation_id, last_msg_id)
                result = {"result": [{"message_id": record["id"], "conversation_id": record["conversation_id"], "author_id": record["author_id"],
                                      "text": record["text"], "picture_id": record["picture_id"], "read": record["read"],
                                      "timestamp": record["timestamp"].isoformat()} for record in records]}
            status = True
            message = json.dumps(result)

            await connection.execute('''UPDATE tagme.message
            SET read = TRUE
            WHERE (conversation_id = $1 AND author_id != $2)''', conversation_id, user_id)
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def get_new_messages(token, conversation_id, last_msg_id):    #Загрузка НОВЫХ сообщений в чате
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('select id, conversation_id, author_id ,text, picture_id, read, timestamp from tagme.message where (conversation_id = $1 and id > $2)',
                                             conversation_id, last_msg_id)
            result = {"result": [{"message_id": record["id"], "conversation_id": record["conversation_id"],"author_id": record["author_id"],
                                  "text": record["text"], "picture_id": record["picture_id"], "read": record["read"],
                                  "timestamp": record["timestamp"].isoformat()} for record in records]}

            await connection.execute('''UPDATE tagme.message
SET read = TRUE
WHERE (conversation_id = $1 AND author_id != $2)''', conversation_id, user_id)
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async def send_message(token, conversation_id, text, picture_id):   #Отправка сообщения
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch(
                '''INSERT INTO tagme.message (conversation_id, author_id, text, picture_id, read, timestamp)
VALUES ($1, $2, $3, $4, FALSE, $5)''', conversation_id, user_id, text, picture_id, datetime.datetime.now())
            result = {"result": [{"conversation_id": record["conversation_id"], "author_id": record["author_id"],
                                  "text": record["text"], "picture_id": record["picture_id"], "read": record["read"],
                                  "timestamp": record["timestamp"]} for record in records]}
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

async  def create_geo_story(token, privacy, picture_id, views, latitude, longitude):
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch(
                '''INSERT INTO tagme.geo_story (creator_id, privacy, picture_id, views, latitude, longitude, timestamp)
VALUES($1, $2, $3, $4, $5, $6, $7)''', user_id, privacy, picture_id, views, latitude, longitude, datetime.datetime.now())
            result = {"result": [{"creator_id": record["creator_id"], "privacy": record["privacy"],
                                  "picture_id": record["picture_id"], "views": record["views"],
                                  "latitude": record["latitude"], "longitude": record["longitude"],
                                  "timestamp": record["timestamp"]} for record in records]}
            status = True
            message = json.dumps(result)
        else:
            status = False
            message = 'token invalid'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
async  def get_geo_story(token, geo_story_id):
    global status, message, tokenManager
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch(
                '''SELECT id, creator_id, privacy, picture_id, views, latitude, longitude, timestamp FROM tagme.geo_story where id = $1''', geo_story_id)
            result = {"result": [{"geo_story_id": record["id"], "creator_id": record["creator_id"],
                                  "privacy": record["privacy"], "picture_id": record["picture_id,"],
                                  "views": record["views"], "latitude": record["latitude"], "longitude": record["longitude"],
                                  "timestamp": record["timestamp"]} for record in records]}
            await connection.execute('''UPDATE tagme.geo_story
            set views = views + 1 
            where id = $1''', geo_story_id)
            status = True
            message = json.dumps(result)
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

            case "get friends":
                token = user_data.get('token')
                await get_friends(token)

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
            case "accept request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                await accept_request(token, user2_id)
            case "cancel request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                await cancel_outgoing_request(token, user2_id)
            case "deny request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                await deny_request(token, user2_id)
            case "get conversations":
                token = user_data.get('token')
                await get_chats(token)
            case "get friend requests":
                token = user_data.get('token')
                await get_friend_requests(token)
            case "get messages":
                token = user_data.get('token')
                last_message_id = user_data.get('last_message_id')
                conversation_id = user_data.get('conversation_id')
                await get_messages(token, conversation_id, last_message_id)
            case "send message":
                token = user_data.get('token')
                conversation_id = user_data.get('conversation_id')
                text = user_data.get('text')
                picture_id = user_data.get('picture_id')
                await send_message(token, conversation_id,  text, picture_id)
            case "get picture":
                token = user_data.get('token')
                picture_id = user_data.get('picture_id')
                await get_picture(token, picture_id)
            case "get new messages":
                token = user_data.get('token')
                last_message_id = user_data.get('last_message_id')
                conversation_id = user_data.get('conversation_id')
                await get_new_messages(token, conversation_id, last_message_id)
            case "get my data":
                token = user_data.get('token')
                await get_my_data(token)
            case _:
                status = False
                message = "action mismatch"

        response = {'action': action, 'status': 'success' if status else 'error', 'message': message}
        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(Websocket, '141.8.193.201', 8765)  # Запуск WebSocket сервера на localhost и порту 8765

asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера