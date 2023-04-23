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
    def __init__(self, list_type):
        self.list_type = list_type
        self.tasks = []

    async def create_thread(self):
        for type in self.list_type:
            task = asyncio.to_thread(self.start_thread, type)
            self.tasks.append(task)
        await asyncio.gather(*self.tasks)

    @staticmethod
    def start_thread(type):
        parser = Parser(type)
        print(f"Старт потока _{type}_: {time.strftime('%X')}")
        time.sleep(0.1)
        asyncio.run(parser.main())
        print(f"Завершение цикла событий _{type}_: {time.strftime('%X')}")


class Parser:
    url_interpol = "https://ws-public.interpol.int/notices/v1/"

    def __init__(self, type, session=None):
        self._type = type
        self.session = session

    async def main(self):
        os.mkdir(f'{self._type}') if not os.path.exists(f"{self._type}") else shutil.rmtree(f'{self._type}')
        async with aiohttp.ClientSession() as self.session:
            iteration = Iteration(self._type, self.session)
            write_file = WriteFile(self._type, self.session)
            # построение url с фильтрами
            for country, gender, age in itertools.product(dict.country_list, dict.gender_list, range(1, 100), ncols=100, position=0, leave=True):
                try:
                    full_url = f'{self.url_interpol}{self._type}?nationality={country}&sexId={gender}&ageMin={age}&ageMax={age}'
                    #print(f"Страна:{country}. Пол:{gender}. Возраст {age}")
                    async with self.session.get(full_url) as json_response:
                        list_json = await json_response.json(content_type=None)
                        if list_json['_embedded']['notices']:
                            path, profile_json, image_link = await iteration.iteration_item_in_list(full_url, list_json)
                            await write_file.write_json(path, profile_json)
                            await write_file.write_image(path, image_link)
                            await asyncio.sleep(0.5)
                        else:
                            #print("Нет данных на запрос")
                            continue
                except Exception as error:
                    print(f"Ошибка при парсинге:\n{error}", traceback.format_exc())
                    await write_file.write_txt(full_url)
                    continue


class Iteration(Parser):
    def __init__(self, type, session):
        self.link_list = []
        super().__init__(type, session)

    async def iteration_pages(self, full_url, list_json):
        # перебор страниц
        for page in range(1, int(list_json['_links']['last']['href'][-1]) + 1):
            async with self.session.get(f'{full_url}&resultPerPage=20&page={page}') as list_response:
                pages_json = await list_response.json(content_type=None)
                return pages_json

    async def iteration_item_in_list(self, full_url, list_json):
        # перебор элементов на странице
        list_json = await self.iteration_pages(full_url, list_json)
        await asyncio.sleep(0.5)
        for item in list_json['_embedded']['notices']:
            if item['_links']['self']['href'] not in self.link_list:
                link = item['_links']['self']['href']
                self.link_list.append(link)
                async with self.session.get(link) as item_response:
                    profile_json = await item_response.json(content_type=None)
                    path = f"{item['name']}_{item['forename']}({item['entity_id'].replace('/', '.')})"
                    image_link = item['_links']['images']['href']
                    return path, profile_json, image_link


class WriteFile(Parser):
    def __init__(self, type, session):
        super().__init__(type, session)

    async def write_txt(self, link):
        # запись url с ошибкой
        with open(f"{self._type}_error_link.txt", 'w') as file:
            file.write(link + '\n')

    async def write_image(self, path, api_images):
        # запись изображений из профиля
        async with self.session.get(api_images) as res_images:
            profile_photo_data = await res_images.json(content_type=None)
            for item_image in profile_photo_data['_embedded']['images']:
                async with self.session.get(f"{api_images}/{item_image['picture_id']}") as res_image:
                    file = await aiofiles.open(f"{self._type}/{path}/{item_image['picture_id']}.jpg", mode='wb')
                    await file.write(await res_image.read())
                    await file.close()

    async def write_json(self, path, data):
        # запись данных json из профиля
        os.makedirs(f'{self._type}/{path}')
        with open(f"{self._type}/{path}/data.json", 'w') as outfile:
            json.dump(data, outfile, indent=2)


if __name__ == '__main__':
    thread = Threading(['yellow', 'red'])
    asyncio.run(thread.create_thread())
