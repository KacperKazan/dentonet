# %%
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from classes import Forum, MainSection, Thread, Post, User
# %%
# Define the URL to scrape
url = "https://dentonet.pl/forum-new/"
base_url = "https://dentonet.pl/forum-new/"
# Send a request to the URL and get the HTML response
response = requests.get(base_url)
html_content = response.content

# Use BeautifulSoup to parse the HTML content
soup = BeautifulSoup(html_content, "html.parser")

# %%
# Find all the div with class 'forabg'
forabgs = soup.find_all('div', {'class': 'forabg'})

main_sections = []

# Loop through each div element with class "forabg"
for forabg in forabgs:
    # Find all a elements with class "forumtitle"
    forumtitles = forabg.find_all('a', {'class': 'forumtitle'})

    header = forabg.find('div', {'class': 'list-inner'})

    if header:
        header_text = header.text.strip()
        header_link = header.a['href']
        header_link = url + header_link

    forums = []
    # Loop through each a element with class "forumtitle"
    
    for forumtitle in forumtitles:
        # Print the text content of the a element
        link = url + forumtitle['href']
        forums.append(Forum(forumtitle.text, link))
    
    main_section = MainSection(header_text, header_link, forums)
    main_sections.append(main_section)

# %%
section = main_sections[0]
forum = section.forums[0]
thread = forum.get_topic_threads(forum.link)[0]
posts = thread.get_all_thread_posts()

# %%
# Create a mongodb that stores all the MainSections, each MainSection has a list of Forums, each Forum has a list of Threads and each Thread has a list of Posts
# each Post and Thread have an author of type User 
# the list of MainSections is stored in a list called 'main_sections'


# %%
from pymongo import MongoClient
# %%

class MongoDB:
    def __init__(self, host, port):
        self.client = MongoClient(host, port)
        self.db = self.client['forum_db']
        self.main_sections = self.db['main_sections']
    
    def insert_main_section(self, main_section):
        main_section_dict = {'name': main_section.name, 'forums': []}
        for forum in main_section.forums:
            forum_dict = {'name': forum.name, 'threads': []}
            for thread in forum.threads:
                thread_dict = {'title': thread.title, 'author': thread.author.to_dict(), 'posts': []}
                for post in thread.posts:
                    post_dict = {'text': post.text, 'author': post.author.to_dict()}
                    thread_dict['posts'].append(post_dict)
                forum_dict['threads'].append(thread_dict)
            main_section_dict['forums'].append(forum_dict)
        self.main_sections.insert_one(main_section_dict)