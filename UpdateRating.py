import asyncio
import asyncpg  # Импорт библиотеки для работы с PostgreSQL
import json
import time

class RatingManager:
    def __init__(self, filename="/home/vgtbl/src/rating.json"):
        self.filename = filename
        self.dictionary = {}
        self._lock = asyncio.Lock()

    def save_rating(self):
        with open(self.filename, "w") as f:
            json.dump(self.dictionary, f)

    async def write_dictionary(self, user_id, place):
        async with self._lock:
            self.dictionary[user_id] = place
            self.dictionary[place] = user_id
            self.save_rating()

ratingManager = RatingManager()
async def update():
    connection = await asyncpg.connect(user='vegetable', password='2kn39fjs', database='db_vegetable',
                                       host='141.8.193.201')
    await connection.execute('''UPDATE tagme.rating
                SET place = (
                    SELECT COUNT(*) + 1
                    FROM tagme.rating AS r2
                    WHERE r2.user_score > rating.user_score
                )''')
    records = await connection.fetch('''SELECT user_id, place from tagme.rating order by place''')
    for record in records:
        await ratingManager.write_dictionary(record["user_id"], record["place"])
async def main():
    while True:
        await update()
        await asyncio.sleep(86400)

if __name__ == "__main__":
    asyncio.run(main())
