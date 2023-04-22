import os
import time
import json
import dict
import shutil
import asyncio
import aiohttp
import aiofiles
import traceback
from tqdm.contrib import itertools


class Threading:
    def __init__(self, type_one, type_two):
        self.yellow = type_one
        self.red = type_two

    async def create_thread(self):
        await asyncio.gather(
            asyncio.to_thread(self.start_thread, self.yellow),
            asyncio.to_thread(self.start_thread, self.red),
        )

    @staticmethod
    def start_thread(type):
        parser = Parser(type)
        print(f"Старт цикла событий _{type}_: {time.strftime('%X')}")
        asyncio.run(parser.main())
        print(f"Завершение цикла событий _{type}_: {time.strftime('%X')}")


class Parser:
    def __init__(self, type):
        self._type = type
        self.iteration = Iteration()
        self.write_file = WriteFile(self._type)
        self.url_interpol = "https://ws-public.interpol.int/notices/v1/"

    async def main(self):
        os.mkdir(f'{self._type}') if not os.path.exists(f"{self._type}") else shutil.rmtree(f'{self._type}')
        async with aiohttp.ClientSession() as session:
            # построение url с фильтрами
            for country, gender, age in itertools.product(dict.country_list, dict.gender_list, range(1, 100), ncols=100, position=0, leave=True):
                try:
                    full_url = f'{self.url_interpol}{self._type}?nationality={country}&sexId={gender}&ageMin={age}&ageMax={age}'
                    # print(f"Страна:{country}. Пол:{gender}. Возраст {age}")
                    async with session.get(full_url) as json_response:
                        list_json = await json_response.json(content_type=None)
                        if list_json['_embedded']['notices']:
                            pages_json = await self.iteration.iteration_pages(session, full_url, list_json)
                            await asyncio.sleep(0.5)
                            path, profile_json, image_link = await self.iteration.iteration_item_in_list(session, pages_json)
                            await self.write_file.write_json(path, profile_json)
                            await self.write_file.write_image(path, session, image_link)
                            await asyncio.sleep(0.5)
                        else:
                            # print("Нет данных на запрос")
                            continue
                except Exception as error:
                    print(f"Ошибка при парсинге:\n{error}", traceback.format_exc())
                    await self.write_file.write_txt(full_url)
                    continue


class Iteration(Parser):
    def __init__(self):
        self.link_list = []

    async def iteration_pages(self, session, full_url, list_json):
        # перебор страниц
        for page in range(1, int(list_json['_links']['last']['href'][-1]) + 1):
            # итоговый запрос
            async with session.get(f'{full_url}&resultPerPage=20&page={page}') as list_response:
                pages_json = await list_response.json(content_type=None)
                return pages_json

    async def iteration_item_in_list(self, session, list_json):
        # перебор элементов в списке на странице
        for item in list_json['_embedded']['notices']:
            if item['_links']['self']['href'] not in self.link_list:
                link = item['_links']['self']['href']
                self.link_list.append(link)
                async with session.get(link) as item_response:
                    profile_json = await item_response.json(content_type=None)
                    path = f"{item['name']}_{item['forename']}({item['entity_id'].replace('/', '.')})"
                    image_link = item['_links']['images']['href']
                    # print(profile_json)
                    return path, profile_json, image_link


class WriteFile(Parser):
    def __init__(self, type):
        self._type = type

    async def write_txt(self, link):
        # запись url с ошибкой
        with open(f"{self._type}_error_link.txt", 'w') as file:
            file.write(link + '\n')

    async def write_image(self, path, session, api_images):
        # запись изображений из профиля
        async with session.get(api_images) as res_images:
            profile_photo_data = await res_images.json(content_type=None)
            for item_image in profile_photo_data['_embedded']['images']:
                async with session.get(f"{api_images}/{item_image['picture_id']}") as res_image:
                    file = await aiofiles.open(f"{self._type}/{path}/{item_image['picture_id']}.jpg", mode='wb')
                    await file.write(await res_image.read())
                    await file.close()

    async def write_json(self, path, data):
        # запись данных json из профиля
        os.makedirs(f'{self._type}/{path}')
        with open(f"{self._type}/{path}/data.json", 'w') as outfile:
            json.dump(data, outfile, indent=2)


if __name__ == '__main__':
    thread = Threading('yellow', 'red')
    asyncio.run(thread.create_thread())