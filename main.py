import asyncio
import aiohttp
import websockets
import json
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import sys
import secrets
import datetime
import vb_vkAPI
import base64

class TokenManager:
    def __init__(self, filename="/home/vgtbl/src/tokens.json"):
        self.filename = filename
        self.dictionary_token = {}
        self._lock = asyncio.Lock()
        self.load_tokens()

    def load_tokens(self):
        try:
            with open(self.filename, "r") as f:
                self.dictionary_token = json.load(f)
        except FileNotFoundError:
            pass

    def save_tokens(self):
        with open(self.filename, "w") as f:
            json.dump(self.dictionary_token, f)

    async def generate_token(self):
        async with self._lock:
            token = secrets.token_urlsafe(16)
            return token

    async def write_dictionary(self, user_id, token):
        async with self._lock:
            self.dictionary_token[user_id] = token
            self.dictionary_token[token] = user_id
            self.save_tokens()

    async def read_dictionary(self, user_id):
        async with self._lock:
            return user_id in self.dictionary_token

    async def get_user_id(self, token):
        async with self._lock:
            return self.dictionary_token.get(token)

    async def pop_dictionary(self, user_id):
        async with self._lock:
            if user_id in self.dictionary_token:
                token = self.dictionary_token.pop(user_id)
                self.dictionary_token.pop(token)
                self.save_tokens()

tokenManager = TokenManager()
async def register_user(username, password): # Регистрация пользователя
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        result = await connection.fetchval('''SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE' ELSE 'FALSE' END AS result''', username)
        if result == 'FALSE':
            token = await tokenManager.generate_token()
            id_string = await connection.fetchval('INSERT INTO tagme."user" (nickname, password) VALUES($1, $2) returning id', username, password)
            id = int(id_string)

            # ------------------------------Рейтинг!!!!--------------------
            await connection.execute('''INSERT INTO tagme.rating (user_id, user_score, place)
VALUES($1, 0, 0) ON CONFLICT (user_id) DO NOTHING''', id)
            # ------------------------------Рейтинг!!!!--------------------

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
    return status, message
async def auth_vk(access_token): # Регистрация пользователя ВК
    global tokenManager
    status = True
    message = ''
    user = await vb_vkAPI.get_user_data(access_token)
    if isinstance(user, vb_vkAPI.User):
        username = f"{user.first_name} {user.last_name} {user.id}"
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        result = await connection.fetchval('''SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE' ELSE 'FALSE' END AS result''', username)
        if result == 'FALSE':
            token = await tokenManager.generate_token()
            picture_status,picture_message = await download_picture(user.photo_200)
            picture_id = 0
            if picture_status:
                picture_id = int(picture_message)

            id_string = await connection.fetchval('INSERT INTO tagme."user" (nickname, picture_id) VALUES($1,$2) returning id', username, picture_id)
            id = int(id_string)

            # ------------------------------Рейтинг!!!!--------------------
            await connection.execute('''INSERT INTO tagme.rating (user_id, user_score, place)
VALUES($1, 0, 0) ON CONFLICT (user_id) DO NOTHING''', id)
            # ------------------------------Рейтинг!!!!--------------------

            await tokenManager.write_dictionary(id, token)
            status = True
            message = token
        else:
            result = await connection.fetchval(
                '''select id from tagme."user" WHERE nickname = $1''', username)
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
    return status, message
async def change_nickname(token, newUserName):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            result = await connection.fetchval(
                '''SELECT CASE WHEN EXISTS (SELECT * FROM tagme."user" WHERE nickname = $1) THEN 'TRUE' ELSE 'FALSE' END AS result''',
                newUserName)
            if result == 'FALSE':
                await connection.execute('''update tagme."user"
set nickname = '$2
where id = $1''', user_id, newUserName)
                status = True
                message = 'success'
            else:
                status = False
                message = 'username already exists'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def login_user(username, password): # Вход пользователя
    global tokenManager
    status = True
    message = ''
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
    return status, message
async def login_token(token): #Вход по токену
    global tokenManager
    status = True
    message = ''
    if await tokenManager.read_dictionary(token):
        status = True
        message = 'success'
    else:
        status = False
        message = 'error'
    return status, message
async def send_location(token, latitude, longitude, accuracy, speed, timestamp): #Обновление location пользователя
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('INSERT INTO tagme.location (user_id, latitude, longitude, accuracy, speed, timestamp) VALUES($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id) DO UPDATE SET latitude = $2, longitude = $3, accuracy = $4, speed = $5, timestamp = $6', user_id, latitude, longitude, accuracy, speed, timestamp)
            status = True
            message = 'success'
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_friends(token): # Получение списка друзей
    global tokenManager
    status = True
    message = ''
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
    return status, message
async def get_locations(token): # получение локации друзей
    global tokenManager
    status = True
    message = ''
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
    return status, message
async def accept_request(token, user2_id): # принятие в друзья
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
   set relation = 'friend', date_linked = $3
   where (relation = 'request_incoming' OR relation = 'request_outgoing') AND
       ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))''', user_id, user2_id, datetime.datetime.now())
            await connection.execute('''INSERT INTO tagme.conversation (user1_id, user2_id)
   SELECT
       $1, $2
   WHERE NOT EXISTS (
       SELECT 1 FROM tagme.conversation WHERE ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1)))''', user_id, user2_id)

            #------------------------------Рейтинг!!!!--------------------
            await connection.execute('''UPDATE tagme.rating
SET user_score = user_score + 1
where user_id = $1 OR user_id = $2''', user_id, user2_id)
            # ------------------------------Рейтинг!!!!--------------------

            status = True
            message = 'success'
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def add_friend(token, nickname): #Отправка заявки в друзья
    global tokenManager
    status = True
    message = ''
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
                return status, message

            isYou = await connection.fetchval('''SELECT CASE
           WHEN ((SELECT id FROM tagme."user" WHERE nickname = $2) = $1) THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isYou == 'TRUE':
                status = False
                message = "Are u retarded?"
                return status, message

            isBlocked = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'blocked') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isBlocked == 'TRUE':
                status = False
                message = 'You have been blocked by this user'
                return status, message

            isFriend = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                       AND user2_id = $1
                                                       AND relation = 'friend') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if isFriend == 'TRUE':
                status = False
                message = 'You are already friends'
                return status, message
            isRequest = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = (SELECT id from tagme."user" where nickname = $2)
                                                        AND user2_id = $1
                                                        AND relation = 'request_outgoing') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, nickname)
            if (isRequest == 'FALSE'):
                await connection.execute("CALL tagme.add_or_update_user_link($1, $2)", str(user_id), nickname)
            else:
                user2_id = await connection.fetchval('''SELECT id from tagme."user" where nickname = $1''', nickname)
                await accept_request(token, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_picture(token, picture_id):   # Загрузка картинки
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT id, picture FROM tagme.picture WHERE (id = $1)''', picture_id)
            result = {"result": [{"picture_id": record['id'], "picture": str(record["picture"])[2:-1]} for record in records]}
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
    return status, message
async def get_my_data(token):   # Получение данных пользователя(по токену)
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetchrow('''SELECT "user".id, "user".nickname, "user".picture_id, user_score FROM tagme."user"
    LEFT JOIN tagme.rating ON user_id = $1
WHERE "user".id = $1''', user_id)
            result = {"user_id": records["id"], "nickname": records["nickname"], "picture_id": records["picture_id"], "user_score": records["user_score"]}
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
    return status, message
async def cancel_outgoing_request(token, user2_id): # Отменить исходящую заявку
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
               set relation = 'default'
               where (relation = 'request_incoming' OR relation = 'request_outgoing') AND
                   ((user1_id = $1 AND user2_id = $2) OR (user1_id = $2 AND user2_id = $1))''', user_id, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
#Вообще эту функцию можно использовать еще как удаление из друзей!
async def deny_request(token, user2_id): # Отклонение запроса в друзья
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link 
SET relation = 'default'
WHERE (user1_id = $1 and user2_id = $2) or (user1_id = $2 and user2_id = $1)''', user_id, user2_id)
            await connection.execute('''UPDATE tagme.rating
            SET user_score = user_score - 1
            where user_id = $1 OR user_id = $2''', user_id, user2_id)
            status = True
            message = 'success'
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_friend_requests(token): # Загрузка списка входящих и исходящих заявок в друзья
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT "user".id AS user_id, nickname, picture.id AS picture_id, relation FROM tagme."user"
         LEFT JOIN tagme.user_link ON tagme."user".id = tagme.user_link.user2_id AND tagme.user_link.user1_id = $1
         LEFT JOIN tagme.picture ON tagme."user".picture_id = tagme.picture.id
WHERE tagme.user_link.relation = 'request_incoming' OR tagme.user_link.relation = 'request_outgoing'
ORDER BY nickname ASC''', user_id)
            result = {"result": [{"user_id": record['user_id'], "nickname": record["nickname"],
                                  "picture_id": record['picture_id'], "relation": record["relation"]} for record in records]}
            status = True
            message = json.dumps((result))
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_chats(token):    #Загрузка чатов
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch('''SELECT conversation.id AS conversation_id, "user".id AS user_id, nickname,  picture.id AS profile_picture_id, author_id, text, message.id AS last_message_id, message.picture_id AS msg_picture_id, read, message.timestamp AS timestamp FROM tagme.conversation
LEFT JOIN tagme."user" ON "user".id = conversation.user1_id OR "user".id = conversation.user2_id
LEFT JOIN tagme.picture ON tagme."user".picture_id = tagme.picture.id
LEFT JOIN tagme.message ON conversation.id = message.conversation_id
WHERE (user1_id = $1 OR user2_id = $1) AND ("user".id != $1) AND (not exists(select * from tagme.message where conversation_id = conversation.id) OR (message.id = (select id from tagme.message where conversation_id = conversation.id order by id desc limit 1)))
''', user_id)
            result = {"result": [{"conversation_id": record['conversation_id'], "user_id": record['user_id'],
                                  "author_id": record["author_id"], "nickname": record['nickname'],
                                  "profile_picture_id": record['profile_picture_id'],
                                  "text": record["text"], "last_message_id": record["last_message_id"], "msg_picture_id": record["msg_picture_id"],
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
    return status, message
async def get_messages(token, conversation_id, last_msg_id):    #Загрузка сообщений в чате
    global tokenManager
    status = True
    message = ''
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
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_new_messages(token, conversation_id, last_msg_id):    #Загрузка НОВЫХ сообщений в чате
    global tokenManager
    status = True
    message = ''
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
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def send_message(token, conversation_id, text, picture_id):   #Отправка сообщения
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            blocked = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT *
                        FROM tagme.user_link
                        WHERE ((user1_id = $1 AND user2_id = (SELECT user2_id FROM tagme.conversation WHERE (user1_id = $1 OR user2_id = $1) AND conversation.id = $2) AND relation = 'blocked')
                            OR (user2_id = $1 AND user1_id = (SELECT user1_id FROM tagme.conversation WHERE (user1_id = $1 OR user2_id = $1) AND conversation.id = $2) AND relation = 'blocked')
                            OR (user1_id = (SELECT user2_id FROM tagme.conversation WHERE (user1_id = $1 OR user2_id = $1) AND conversation.id = $2) AND user2_id = $1 AND relation = 'blocked')
                            OR (user2_id = (SELECT user1_id FROM tagme.conversation WHERE (user1_id = $1 OR user2_id = $1) AND conversation.id = $2) AND user1_id = $1 AND relation = 'blocked'))) THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, conversation_id)
            if blocked == 'FALSE':
                await connection.fetch(
                    '''INSERT INTO tagme.message (conversation_id, author_id, text, picture_id, read, timestamp)
    VALUES ($1, $2, $3, $4, FALSE, $5)''', conversation_id, user_id, text, picture_id, datetime.datetime.now())
                message = "success"
            else:
                message = "you cannot"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def create_geo_story(token, privacy, picture_id, latitude, longitude):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute(
                '''INSERT INTO tagme.geo_story (creator_id, privacy, picture_id, views, latitude, longitude, timestamp)
VALUES($1, $2, $3, 0, $4, $5, $6)''', user_id, privacy, picture_id, latitude, longitude, datetime.datetime.now())
            await connection.execute('''UPDATE tagme.rating
            SET user_score = user_score + 1
            where user_id = $1''', user_id)
            status = True
            message = "success"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def get_geo_stories(token):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            records = await connection.fetch(
                '''SELECT geo_story.id AS geo_story_id, geo_story.timestamp, geo_story.picture_id, geo_story.views,geo_story.latitude, geo_story.longitude, geo_story.creator_id, nickname, "user".picture_id AS profile_picture_id, geo_story.privacy FROM tagme.geo_story
    LEFT JOIN tagme.location ON tagme.location.user_id = $1
    LEFT JOIN tagme.user_link AS user_link_to_user ON user_link_to_user.user1_id = creator_id AND user_link_to_user.user2_id = $1
    LEFT JOIN tagme.user_link AS user_link_from_user ON user_link_from_user.user1_id = $1 AND user_link_from_user.user2_id = creator_id
    LEFT JOIN tagme.user ON tagme."user".id = geo_story.creator_id
WHERE ((tagme.geo_story.timestamp::timestamptz > now() - interval '21 hour') AND (
    (
        (
            acos(
                    least(
                            greatest(
                                    sin(radians(tagme.location.latitude)) * sin(radians(geo_story.latitude)) +
                                    cos(radians(tagme.location.latitude)) * cos(radians(geo_story.latitude)) *
                                    cos(radians(geo_story.longitude) - radians(tagme.location.longitude)),
                                    -1.0
                            ),
                            1.0
                    )
            ) * 6371
            ) < 0.7 AND privacy = 'global' AND ((user_link_to_user IS NULL OR user_link_to_user.relation != 'blocked') AND (user_link_from_user IS NULL OR user_link_from_user.relation != 'blocked')))
        OR (user_link_to_user.relation = 'friend') OR (creator_id = $1)))''', user_id)
            result = {"result": [{"geo_story_id": record["geo_story_id"], "timestamp": record["timestamp"].isoformat(), "views":record["views"],
                                  "picture_id": record["picture_id"], "creator_id": record["creator_id"], "latitude": record["latitude"],
                                  "longitude": record["longitude"], "nickname": record["nickname"], "profile_picture_id":record["profile_picture_id"],
                                  "privacy":record["privacy"]} for record in records]}
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
    return status, message
async def add_view_to_geo_story(token, geo_story_id):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.geo_story
set views = views + 1
where id = $1''', geo_story_id)
            await connection.execute('''UPDATE tagme.rating set user_score = user_score + 1 where user_id = (select creator_id from tagme.geo_story where id = $1)''', geo_story_id)
            status = True
            message = "success"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def insert_picture(token, picture):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            result = await connection.fetchval(
                '''INSERT INTO tagme.picture (picture)
values ($1) RETURNING id''', bytearray(picture, encoding="utf-8"))
            status = True
            message = result
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def download_picture(url):
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                image_content = await response.read()
                base64_image = base64.b64encode(image_content)
                result = await connection.fetchval(
                    '''INSERT INTO tagme.picture (picture) values ($1) RETURNING id''', base64_image)
            status = True
            message = result
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def load_profile(token, profile_user_id):
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            relation = await connection.fetchval(
                '''SELECT relation from tagme.user_link where user1_id = $1 AND user2_id = $2''', user_id,
                profile_user_id)

            blocked_by_user2 = await connection.fetchval('''SELECT CASE
           WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = $2 AND user2_id = $1 AND relation = 'blocked') THEN 'TRUE'
           ELSE 'FALSE'
           END AS result''', user_id, profile_user_id)
            if blocked_by_user2 == 'TRUE':
                relation = 'block_incoming'

            you_block_user = await connection.fetchval('''SELECT CASE
                       WHEN EXISTS (SELECT * FROM tagme.user_link WHERE user1_id = $1 AND user2_id = $2 AND relation = 'blocked') THEN 'TRUE'
                       ELSE 'FALSE'
                       END AS result''', user_id, profile_user_id)
            if you_block_user == 'TRUE':
                relation = 'block_outgoing'

            if (you_block_user == 'TRUE' and blocked_by_user2 == 'TRUE'):
                relation = 'block_mutual'

            friend_count = await connection.fetchval('''SELECT count(user2_id) from tagme.user_link where user1_id = $1 AND relation = \'friend\'''', profile_user_id)

            records = await connection.fetchrow('''SELECT nickname, picture_id, date_linked, user_score from tagme."user"
    LEFT JOIN tagme.user_link ON user1_id = $1 AND user2_id = $2
    LEFT JOIN tagme.rating ON user_id = $2
where "user".id = $2''',user_id ,profile_user_id)

            result = {"nickname": records["nickname"], "picture_id": records["picture_id"], "relation" : relation if relation else None, "friend_count" : friend_count,
                      "user_score" : records["user_score"], "date_linked" : records["date_linked"].isoformat() if records["date_linked"] else None}

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
    return status, message
async def delete_friend(token, user2_id):       #Удаление пользователя user2_id из друзей
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
SET relation = 'default'
WHERE (user1_id = $1 and user2_id = $2) or (user1_id = $2 and user2_id = $1)''', user_id, user2_id)
            status = True
            message = "success"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def block_user(token, user2_id):       #Удаление пользователя user2_id из друзей
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute("CALL tagme.block_user($1, $2)", str(user_id), str(user2_id))
            status = True
            message = "success"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def unblock_user(token, user2_id):       #Удаление пользователя user2_id из друзей
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme.user_link
SET relation = 'default'
WHERE (user1_id = $1 and user2_id = $2)''', user_id, user2_id)
            status = True
            message = "success"
        else:
            status = False
            message = 'invalid token'
    except:
        message = str(sys.exc_info()[1])
        status = False
    finally:
        await connection.close()
    return status, message
async def set_profile_picture(token, picture_id): #Обновление location пользователя
    global tokenManager
    status = True
    message = ''
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable', host='141.8.193.201')
    try:
        if await tokenManager.read_dictionary(token):
            user_id = await tokenManager.get_user_id(token)
            await connection.execute('''UPDATE tagme."user"
SET picture_id = $2
WHERE id = $1''', user_id, picture_id)
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
    return status, message
async def rating_update_task(update_interval):
    while True:
        connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                           host='141.8.193.201')
        await connection.execute('''UPDATE tagme.rating
            SET place = (
                SELECT COUNT(*) + 1
                FROM tagme.rating AS r2
                WHERE r2.user_score > rating.user_score
            )''')
        await asyncio.sleep(update_interval)  # Wait for the specified interval
async def Websocket(websocket, path):
    global tokenManager
    status = True
    message = ''
    while True:
        data = await websocket.recv()  # Получение данных от клиента
        user_data = json.loads(data)  # Преобразование полученных данных из JSON в объект Python
        action = user_data.get("action")
        request_id = user_data.get("request_id")

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
                        status, message = await register_user(username, password)
                    else:
                        message = 'input_error:' + ', '.join(error_list)
                else:
                    message = 'no login or password'
            case "login":
                username = user_data.get('username')
                password = user_data.get('password')
                status, message = await login_user(username, password)
            case "auth vk":
                access_token = user_data.get('access_token')
                status, message = await auth_vk(access_token)
            case "change nickname":
                token = user_data.get('token')
                newUserName = user_data.get('')
                status, message = await change_nickname(token, newUserName)
            case "validate token":
                token = user_data.get('token')
                status, message = await login_token(token)
            case "get friends":
                token = user_data.get('token')
                status, message = await get_friends(token)
            case "send location":
                token = user_data.get('token')
                latitude = float(user_data.get('latitude'))
                longitude = float(user_data.get('longitude'))
                accuracy = float(user_data.get('accuracy'))
                speed = float(user_data.get('speed'))
                timestamp = datetime.datetime.now()
                status, message = await send_location(token, latitude, longitude, accuracy, speed, timestamp)
            case "get locations":
                token = user_data.get('token')
                status, message = await get_locations(token)
            case "add friend":
                token = user_data.get('token')
                nickname = user_data.get('nickname')
                status, message = await add_friend(token, nickname)
            case "delete friend":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await delete_friend(token, user2_id)
            case "block user":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await block_user(token, user2_id)
            case "unblock user":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await unblock_user(token, user2_id)
            case "accept request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await accept_request(token, user2_id)
            case "cancel request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await cancel_outgoing_request(token, user2_id)
            case "deny request":
                token = user_data.get('token')
                user2_id = user_data.get('user2_id')
                status, message = await deny_request(token, user2_id)
            case "get conversations":
                token = user_data.get('token')
                status, message = await get_chats(token)
            case "get friend requests":
                token = user_data.get('token')
                status, message = await get_friend_requests(token)
            case "get messages":
                token = user_data.get('token')
                last_message_id = user_data.get('last_message_id')
                conversation_id = user_data.get('conversation_id')
                status, message = await get_messages(token, conversation_id, last_message_id)
            case "send message":
                token = user_data.get('token')
                conversation_id = user_data.get('conversation_id')
                text = user_data.get('text')
                picture_id = user_data.get('picture_id')
                status, message = await send_message(token, conversation_id,  text, picture_id)
            case "get picture":
                token = user_data.get('token')
                picture_id = user_data.get('picture_id')
                status, message = await get_picture(token, picture_id)
            case "get new messages":
                token = user_data.get('token')
                last_message_id = user_data.get('last_message_id')
                conversation_id = user_data.get('conversation_id')
                status, message = await get_new_messages(token, conversation_id, last_message_id)
            case "get my data":
                token = user_data.get('token')
                status, message = await get_my_data(token)
            case "insert picture":
                token = user_data.get('token')
                picture = user_data.get('picture')
                status, message = await insert_picture(token, picture)
            case "create geo story":
                token = user_data.get('token')
                privacy = user_data.get('privacy')
                picture_id = user_data.get('picture_id')
                latitude = float(user_data.get('latitude'))
                longitude = float(user_data.get('longitude'))
                status, message = await create_geo_story(token, privacy, picture_id, latitude, longitude)
            case "get geo stories":
                token = user_data.get('token')
                status, message = await get_geo_stories(token)
            case "add view to geo story":
                token = user_data.get('token')
                geostory_id = user_data.get('geostory_id')
                status, message = await add_view_to_geo_story(token, geostory_id)
            case "set profile picture":
                token = user_data.get('token')
                picture_id = user_data.get('picture_id')
                status, message = await set_profile_picture(token, picture_id)
            case "load profile":
                token = user_data.get('token')
                profile_user_id = user_data.get('user_id')
                status, message = await load_profile(token, profile_user_id)
            case _:
                status = False
                message = "action mismatch"

        response = {'action': action, 'status': 'success' if status else 'error', 'request_id': request_id,'message': message}
        await websocket.send(json.dumps(response))  # Отправка ответа клиенту в формате JSON


start_server = websockets.serve(Websocket, '141.8.193.201', 8765)  # Запуск WebSocket сервера на localhost и порту 8765
asyncio.get_event_loop().run_until_complete(start_server)  # Запуск сервера и ожидание его завершения
asyncio.get_event_loop().run_forever()  # Бесконечный цикл для работы WebSocket сервера