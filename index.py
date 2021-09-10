import asyncio
from datetime import datetime
import re
from typing import Dict, List

import aiofiles
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from bs4.element import Tag

URL = "https://taifaleo.nation.co.ke/"


def get_page_count(html_doc: BeautifulSoup) -> int:
    """
    Finds the pagination footer on the home page and returns the number of
    pages available including the current home page.
    """
    max_page_li_element = html_doc.select_one(
        "ul.pagination > li:nth-last-child(2)")
    if max_page_li_element is not None:
        return int(max_page_li_element.text)
    return 0


async def download_page(session: ClientSession, url: str, params: Dict[str, int] = {}) -> str:
    # TODO: Add error handling
    async with session.get(url, params=params) as resp:
        return await resp.text()


def get_articles(html_doc: BeautifulSoup) -> List[str]:
    post_elements = html_doc.select("div.post")
    if post_elements is not None:
        return [get_article(post_elem) for post_elem in post_elements]
    else:
        return []


def get_article(post_elem: Tag) -> str:
    article_text = ""
    title = post_elem.find("h2", class_="entry-title")
    content_root = post_elem.find("div", class_="entry-content")
    if title is not None and isinstance(title, Tag):
        article_text += title.get_text() + "\n"
    if content_root is not None and isinstance(content_root, Tag):
        had_location_text = False
        for i, p_tag in enumerate(content_root.find_all("p")):
            if i == 0:
                # The first p tag is the author
                article_text += p_tag.get_text()
            elif i == 1:
                # The following p tag may either be the summary or
                # a description of the location being reported
                had_location_text = re.search(
                    r"^[A-Z]+, (\w+ ?){1,2}$", p_tag.get_text()) is not None
                if had_location_text:
                    article_text += " " + p_tag.get_text() + "\n"
                else:
                    article_text += "\n" + p_tag.get_text()
            elif i == 2:
                # Ensure that the core text doesn't begin with a space
                if had_location_text:
                    article_text += p_tag.get_text() + "\n"
                else:
                    article_text += " " + p_tag.get_text() + "\n"
            else:
                article_text += " " + p_tag.get_text().strip()
    return article_text


async def save_to_file(file_name: str, articles: List[str], mode='w'):
    async with aiofiles.open(file_name, mode) as f:
        for article in articles:
            await f.write(article)
            await f.write("\n" + "-" * 10 + "\n")


async def download_and_save(session: ClientSession, file_name: str, index: int):
    """
    Combines downloading and saving to file
    """
    html_text = await download_page(session, URL,  {'paged': index})
    html_doc = BeautifulSoup(html_text, 'html.parser')

    articles = get_articles(html_doc)
    await save_to_file(file_name, articles, mode='a')


async def run():
    async with ClientSession() as session:
        html_text = await download_page(session, URL)
        html_doc = BeautifulSoup(html_text, 'html.parser')

        page_count = get_page_count(html_doc)
        print(f"Downloading articles from {page_count} pages")

        articles = get_articles(html_doc)
        today = datetime.now().strftime("%d-%m-%Y")
        file_name = f"taifa-leo-{today}.txt"
        await save_to_file(file_name, articles)

        tasks = []
        for i in range(2, page_count):
            tasks.append(asyncio.ensure_future(
                download_and_save(session, file_name, i)))

        await asyncio.gather(*tasks)


def main():
    """
    - download index page
        - look at nav bar for page count
        - download remaining pages
    - for each page:
        - get articles and remove author
    - save all the text with dash delimiters
    - profit
    """
    formatter = "%b %d %Y %H:%M:%S"
    now = datetime.now().strftime(formatter)
    print(f"Starting script at {now}...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    finished = datetime.now().strftime(formatter)
    print(f"Finished at {finished}!")


if __name__ == "__main__":
    main()
