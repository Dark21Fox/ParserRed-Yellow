import os
import time
import json
import dict
import shutil
import asyncio
import aiohttp
import aiofiles
import traceback
from tqdm.contrib.itertools import product

link_list = []
url_interpol = "https://ws-public.interpol.int/notices/v1/"


class Parser:
    def __init__(self, type):
        self.type = type

    async def main(self):
        os.mkdir(f'{self.type}') if not os.path.exists(f"{self.type}") else shutil.rmtree(f'{self.type}')
        async with aiohttp.ClientSession() as session:
            # построение url с фильтрами
            for country, gender, age in product(dict.country_list, dict.gender_list, range(1, 100), ncols=100, position=0, leave=True):
                try:
                    full_url = f'{url_interpol}{self.type}?nationality={country}&sexId={gender}&ageMin={age}&ageMax={age}'
                    #print(f"Страна:{country}. Пол:{gender}. Возраст {age}")
                    async with session.get(full_url) as json_response:
                        list_json = await json_response.json()
                        if list_json['_embedded']['notices']:
                            await self.iteration_pages(session, full_url, list_json)
                        else:
                            # print("Нет данных на запрос")
                            continue
                except Exception as error:
                    print(f"Ошибка при парсинге:\n{error}", traceback.format_exc())
                    continue

    async def iteration_pages(self, session, full_url, list_json):
        # перебор страниц
        for page in range(1, int(list_json['_links']['last']['href'][-1]) + 1):
            time.sleep(0.2)
            # итоговый запрос
            async with session.get(f'{full_url}&resultPerPage=20&page={page}') as list_response:
                list_json = await list_response.json()
                await self.iteration_item_in_list(session, list_json)
                time.sleep(0.25)

    async def iteration_item_in_list(self, session, list_json):
        # перебор элементов в списке на странице
        for item in list_json['_embedded']['notices']:
            if item['_links']['self']['href'] not in link_list:
                link = item['_links']['self']['href']
                link_list.append(link)
                async with session.get(link) as item_response:
                    profile_json = await item_response.json()
                    path = f"{item['name']}_{item['forename']}({item['entity_id'].replace('/', '.')})"
                    await self.write_json(path, profile_json)
                    await self.write_image(path, session, item['_links']['images']['href'])
                    # print(profile_json)
                    time.sleep(0.5)

    async def write_image(self, path, session, api_images):
        # запись изображений из профиля
        async with session.get(api_images) as res_images:
            profile_photo_data = await res_images.json()
            for item_image in profile_photo_data['_embedded']['images']:
                async with session.get(f"{api_images}/{item_image['picture_id']}") as res_image:
                    file = await aiofiles.open(f"{self.type}/{path}/{item_image['picture_id']}.jpg", mode='wb')
                    await file.write(await res_image.read())
                    await file.close()

    async def write_json(self, path, data):
        # запись данных json из профиля
        os.makedirs(f'{self.type}/{path}')
        with open(f"{self.type}/{path}/data.json", 'w') as outfile:
            json.dump(data, outfile, indent=2)


def start_thread(type):
    class_parser = Parser(type)
    print(f"Старт цикла событий _{type}_: {time.strftime('%X')}")
    asyncio.run(class_parser.main())
    print(f"Завершение цикла событий _{type}_: {time.strftime('%X')}")


async def create_thread():
    await asyncio.gather(
        asyncio.to_thread(start_thread, 'yellow'),
        asyncio.to_thread(start_thread, 'red'),
    )


if __name__ == '__main__':
    asyncio.run(create_thread())