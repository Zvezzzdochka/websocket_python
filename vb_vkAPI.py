import aiohttp
import asyncio
from dataclasses import dataclass
from typing import List


@dataclass
class VkResponse:
    response: List['User']


@dataclass
class User:
    id: int
    first_name: str
    last_name: str
    photo_200: str


class VkApiService:
    BASE_URL = "https://api.vk.com/method/"

    def __init__(self, access_token):
        self.access_token = access_token

    async def get_users(self, fields):
        api_version = "5.199"
        url = f"{self.BASE_URL}users.get"
        params = {
            "access_token": self.access_token,
            "fields": fields,
            "v": api_version
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()  # Raise exception for bad response status
                    json_response = await response.json()
                    users_data = self.extract_users_data(json_response)
                    users_list = [self.create_user_from_data(user_data) for user_data in users_data]

                    return VkResponse(response=users_list)

        except aiohttp.ClientResponseError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as err:
            print(f"Other error occurred: {err}")
            raise

    def extract_users_data(self, json_response):
        if 'response' in json_response:
            return json_response['response']
        elif 'items' in json_response:
            return json_response['items']
        else:
            raise ValueError("Unable to extract users data from JSON response")

    def create_user_from_data(self, user_data):
        return User(
            id=user_data.get('id', 0),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', ''),
            photo_200=user_data.get('photo_200', '')
        )


# Пример использования:
async def get_user_data(access_token):
    api = VkApiService(access_token)
    fields = "id,first_name,last_name,photo_200"

    try:
        vk_response = await api.get_users(fields)
        if vk_response.response:
            return vk_response.response[0]  # Возвращаем первый объект User из списка
    except Exception as err:
        return err