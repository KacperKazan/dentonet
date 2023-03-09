################################################################################
# %% Classes
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re
# %%
# Define the URL to scrape
url = "https://dentonet.pl/forum-new/"
base_url = "https://dentonet.pl/forum-new/"
# Send a request to the URL and get the HTML response

import urllib.parse

def remove_sid_from_link(link):
    # remove sid from link
    parsed_url = urllib.parse.urlparse(link)
    query_string = urllib.parse.unquote_plus(parsed_url.query)
    query_string = '&'.join([param for param in query_string.split('&') if not param.startswith('sid')])
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{query_string}"

def convert_url_to_file_path(url, local_root_path):
    parsed_url = urllib.parse.urlparse(url)
    path_components = parsed_url.path.strip("/").split("/")
    query_string = urllib.parse.unquote_plus(parsed_url.query) if parsed_url.query else ""
    file_name = f"{parsed_url.path.split('/')[-1]}_{query_string}.html" if parsed_url.path.endswith(".php") else "index.html"
    return f"{local_root_path}\\{'_'.join(path_components)}_{file_name}"

def request_with_retry(url, retry_count=10):
    response = None
    for i in range(retry_count):
        try:
            response = requests.get(url)

            # with open(convert_url_to_file_path(url, 'html'), 'w', encoding="utf-8" ) as f:
            #     f.write(response.text)
            
            break
        except Exception as e:
            print(e)
            print(f'Failed to get response from {url}. Retrying...')
            # output url to file 'failed_urls.txt'
            with open('failed_urls.txt', 'a') as f:
                f.write(url + '\n')
        # sleep for 1 second
        time.sleep(1)
    return response

response = request_with_retry(base_url)
html_content = response.content

# Use BeautifulSoup to parse the HTML content
soup = BeautifulSoup(html_content, "html.parser")

# %%
polish_months = {
    'stycznia': 1,
    'lutego': 2,
    'marca': 3,
    'kwietnia': 4,
    'maja': 5,
    'czerwca': 6,
    'lipca': 7,
    'sierpnia': 8,
    'września': 9,
    'października': 10,
    'listopada': 11,
    'grudnia': 12
}

def parse_datetime(text):
    text  = text.strip().replace('»', '')
    # trim text after '\n'
    text = text.split('\n')[0].strip()
    for month_name, month_number in polish_months.items():
        text = text.replace(month_name, str(month_number))

    format = "%d %m %Y, %H:%M"
    date_time = datetime.strptime(text, format)
    return date_time

# %%
def is_last_page(url):
    # get 'active' li element from pagination and check if it's the last in the list
    # Send a request to the URL and get the HTML response
    response = request_with_retry(url)
    html_content = response.content

    # Use BeautifulSoup to parse the HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    pagination = soup.find('div', {'class': 'pagination'})
    if pagination:
        active_page = pagination.find('li', {'class': 'active'})
        if active_page:
            next_page = active_page.find_next_sibling('li')
            if next_page:
                return False
            else:
                return True
    return True

# %%
class MainSection:
    def __init__(self, header_text, header_link, forums):
        self.header_text = header_text
        self.header_link = header_link
        self.forums = forums
    
    def __dict__(self):
        # note: this does not include forums
        return {
            'header_text': self.header_text,
            'header_link': self.header_link,
        }
    
    def __str__(self):
        # return header_text, link followed by tab indented list of forums
        return self.header_text  + '\n' + self.header_link + '\n' + '\t' + '\n\t'.join(str(forum) for forum in self.forums)

class User:
    def __init__(self, username):
        self.username = username

    def __dict__(self):
        return {
            'username': self.username,
        }

    def __str__(self):
        return self.username
    


class Forum:
    def __init__(self, title, link):
        self.title = title
        link = remove_sid_from_link(link)
        self.link = link
        self.increment = 25

    def get_page_link_at_index(self, idx):
        return self.link + f'&start={idx * self.increment}'
    
    def __dict__(self):
        return {
            'title': self.title,
            'link': self.link,
        }
    
    def __str__(self):
        # title followed by link on separate line
        return self.title + '\n' + self.link

    def get_topic_announcements(self):
        return self._get_topic_threads(self.link, is_announcement=True)

    def _get_topic_threads(self, url, is_announcement=False):
        try:
            # Send a request to the URL and get the HTML response
            response = request_with_retry(url)
            html_content = response.content

            # Use BeautifulSoup to parse the HTML content
            soup = BeautifulSoup(html_content, "html.parser")

            annoucements = set(soup.find_all('div', {'class': 'forumbg announcement'}))
            if is_announcement:
                forabgs = annoucements
            else:
                forabgs = set(soup.find_all('div', {'class': 'forumbg'}))
                forabgs -= annoucements

            main_sections = []

            # Loop through each div element with class "forabg"
            for forabg in forabgs:
                # Find all a elements with class "forumtitle"
                forumtitles = forabg.find_all('a', {'class': 'topictitle'})
                topics_table = forabg.find('ul', {'class': 'topiclist topics'})
                topics = topics_table.find_all('li', {'class': 'row'})

                topic_threads = []
                # Loop through each a element with class "forumtitle"
                
                for topic in topics:
                    topic_title = topic.find('a', {'class': 'topictitle'})
                    topic_name = topic_title.text
                    topic_link = base_url + topic_title['href']

                    # topic_pagination = topic.find('div', {'class': 'pagination'})
                    # if topic_pagination:
                    #     # get last li element from pagination
                    #     last_page = topic_pagination.find_all('li')[-1]
                    #     # get last page text
                    #     last_page_text = int(last_page.text)
                    #     print
                
                    # get class posts from topic
                    posts = topic.find('dd', {'class': 'posts'})
                    # get text from posts, extract number of replies using regex
                    num_replies = int(re.search(r'\d+', posts.text).group())

                    # if num_replies > 250:
                    #     # write topic_link to file 'too_many_replies.txt'
                    #     with open('too_many_replies.txt', 'a') as f:
                    #         f.write(topic_link + '\n')
                    #     continue

                    meta = topic.find('div', {'class': 'responsive-hide'})

                    username = meta.find('a', {'class': 'username'})
                    if not username:
                        username = meta.find('span', {'class': 'username'})

                    username = username.text.strip() if username else None
                    user = User(username)

                    date_time = None
                    for child in meta.children:
                        # if child is NavigationString, convert to string else get child.text
                        # if child has no attribute text, cast it as string else get child.text
                        if hasattr(child, 'text'):
                            child_text = child.text
                        else:
                            child_text = str(child)
                        if '»' in child_text:
                            date_time = parse_datetime(child_text)
                    
                    thread = Thread(topic_name, topic_link, user, date_time, num_replies)

                    yield thread
                    # topic_threads.append(thread)

                    # return topic_threads
        except Exception as e:
            print(e)
            print('url: \n', url)


    def get_all_forum_threads(self):
        # TODO: get rid of this
        i = 0

        keep_going = True
        while keep_going:
            url  = self.get_page_link_at_index(i)
            
            for elem in self._get_topic_threads(url):
                yield elem

            i += 1
            if is_last_page(url):
                keep_going = False

class Post:
    def __init__(self, postcontent):
        # 'content' class and extract the text
        # get the 'author' class and extract the text
        content = postcontent.find('div', {'class': 'content'})
        if content:
            content_html = str(content)
            content = content.text.strip()
        else:
            content_html = ''
            content = ''

        author_p = postcontent.find('p', {'class': 'author'})
        
        user = None
        datetime = None
        if author_p is not None:
            # get username class from author_p and extract the text
            username = author_p.find('span', {'class': 'username'})
            if username is None:
                username  = author_p.find('a', {'class': 'username'})
            username = username.text.strip() if username else None
            user = User(username)

            # get last child element of author_p and extract the text
            last = author_p.contents[-1]
            # last is NavigationString, so we need to convert it to string
            datetime = parse_datetime(str(last)) if last else None

        self.author = user
        self.datetime = datetime
        self.content = content
        self.html = content_html
    
    def __dict__(self):
        return {
            'author': self.author.__dict__(),
            'datetime': self.datetime,
            'content': self.content,
            'html': self.html,
        }
       
    def __str__(self):
        return self.author.username + '\n' + str(self.datetime) + '\n' + self.content + '\n' + self.html
    

class Thread:
    def __init__(self, title, link, author, date, num_replies):
        self.title = title
        link = remove_sid_from_link(link)
        self.link = link
        self.author = author
        self.date = date
        self.num_replies = num_replies
        self.increment = 15


    def get_page_link_at_index(self, idx):
        return self.link + f'&start={idx * self.increment}'
    
    def __dict__(self):
        return {
            'title': self.title,
            'link': self.link,
            'author': self.author.__dict__(),
            'date': self.date,
            'num_replies': self.num_replies,
        }
    
    def __str__(self):
        # title followed by link on separate line
        return self.title + '\n' + self.link + '\n' + str(self.author) + '\n' + str(self.date) + '\n' + str(self.num_replies)

    def _get_thread_posts(self, url):
        # get all 'post' class from thread.link
        # loop through each post and parse it with parse_post()
        # return list of parsed posts
        response = request_with_retry(self.link)
        html_content = response.content

        # Use BeautifulSoup to parse the HTML content
        soup = BeautifulSoup(html_content, "html.parser")

        posts = soup.find_all('div', {'class': 'post'})
        for post in posts:
            parsed_post = Post(post)
            yield parsed_post

    def get_all_thread_posts(self):
        idx = 0
        keep_going = True
        posts = []
        while keep_going:
            url = self.get_page_link_at_index(idx)
            for thread_post in self._get_thread_posts(url):
                yield thread_post
            idx += 1
            if is_last_page(url):
                keep_going = False

################################################################################
################################################################################
################################################################################
# %%
import requests
from bs4 import BeautifulSoup
from datetime import datetime
# %%
# Define the URL to scrape
url = "https://dentonet.pl/forum-new/"
base_url = "https://dentonet.pl/forum-new/"
# Send a request to the URL and get the HTML response
response = request_with_retry(base_url)
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
# %%
import pymongo
from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId
from tqdm import tqdm

client = MongoClient()
db = client['forums']
# %%
# Create a mongodb that stores all the MainSections, each MainSection has a list of Forums, each Forum has a list of annoucnement Threads and also general threads (all threads). each Thread has a list of Posts
# each Post and Thread have an author of type User 
# the list of MainSections is stored in a list called 'main_sections'
# %%
def check_link_in_collection(link, collection):
    # TODO: temporary when creating a new collection
    query = {'$or': [{'link': link}, {'threads.link': link}]}
    result = collection.find_one(query)
    out = result is not None
    return out
# %%
total_threads = 28918
total_threads = 4628 # for Forum ogólnostomatologiczne
p_bar = tqdm(total=total_threads)
for main_section in main_sections:
    break
    for forum in main_section.forums:
        # Insert forum object into MongoDB collection
        if forum.title != 'Forum ogólnostomatologiczne':
            continue

        collection = db[forum.title]
        f_dict = forum.__dict__()
        f_dict['section'] = main_section.header_text

        for thread in forum.get_topic_announcements():
            if check_link_in_collection(thread.link, collection):
                p_bar.update(1)
                continue
            # Create a list for the posts
            posts_list = []
            for post in tqdm(thread.get_all_thread_posts(), total=thread.num_replies, leave=False):
                # Append post object to posts list
                posts_list.append(post.__dict__())
            # Insert thread object to MongoDB collection
            thread_doc = thread.__dict__()
            # Add posts list to thread object
            thread_doc['posts'] = posts_list
            thread_doc['announcement'] = True
            thread_doc['forum'] = f_dict # this not really necessary but doesn't take up too much memory
            # insert thread_doc into collection
            thread_result = collection.insert_one(thread_doc)
            # thread_result = collection.update_one(
            #     {"_id": forum_result.inserted_id},
            #     {"$push": {"threads": thread_doc}})
            p_bar.update(1)

        for thread in forum.get_all_forum_threads():
            if check_link_in_collection(thread.link, collection):
                p_bar.update(1)
                continue

            # Create a list for the posts
            posts_list = []
            for post in tqdm(thread.get_all_thread_posts(), total=thread.num_replies, leave=False):
                # Append post object to posts list
                posts_list.append(post.__dict__())
            # Insert thread object to MongoDB collection
            thread_doc = thread.__dict__()
            # Add posts list to thread object
            thread_doc['posts'] = posts_list
            thread_doc['announcement'] = False
            thread_doc['forum'] = f_dict
            # insert thread_doc into collection
            try: 
                thread_result = collection.insert_one(thread_doc)
                # thread_result = ms_collection.update_one(
                #     {"_id": forum_result.inserted_id},
                #     {"$push": {"threads": thread_doc}})
            except pymongo.errors.WriteError as e:
                print(e)
                print(thread.link)
                # write thread.link to a file 'thread_too_big.txt'
                with open('thread_too_big.txt', 'a') as f:
                    f.write(thread.link + '\n')
            except pymongo.errors.DuplicateKeyError as e:
                print(e)
                print(thread.link)
                with open('duplicate_threads.txt', 'a') as f:
                    f.write(thread.link + '\n')
            except Exception as e:
                print(e)
                print(thread.link)
                with open('other_errors.txt', 'a') as f:
                    f.write(thread.link + '\n')
                
            p_bar.update(1)
p_bar.close()
print('Done')
# %%
# print all collections in the database
# for collection in db.list_collection_names():
#     print(collection)
#     print(db[collection].find_one())

# %%
# # ## clear the whole database db
# for collection in db.list_collection_names():
#     db.drop_collection(collection)
# %%
# %%
# get schema of x recursively going through all keys, returns a nested dict with all keys and their types
def get_schema(x):
    if isinstance(x, dict):
        schema = {}
        for key in x.keys():
            schema[key] = get_schema(x[key])
        return schema
    if isinstance(x, list):
        schema = []
        for item in x:
            schema.append(get_schema(item))
            break
        return schema
    else:
        return type(x)

for collection in db.list_collection_names():
    x  = db[collection].find_one()
    print(x)
get_schema(x)
# %%
# clone the database to a new database
# def clone_database(db_name, new_db_name):
#     client = MongoClient()
#     db = client[db_name]
#     new_db = client[new_db_name]
#     for collection in db.list_collection_names():
#         print(collection)
#         for doc in db[collection].find():
#             new_db[collection].insert_one(doc)
# clone_database('dentonet', 'dentonet2')
# # %%
# %%
link = 'https://dentonet.pl/forum-new/./viewtopic.php?f=1&t=22411&sid=7e21eeb117ec3beee28e8ac4233ff846'
link = 'https://dentonet.pl/forum-new/./viewtopic.php?f=1&t=22431&sid=7e21eeb117ec3beee28e8ac4233ff846'
link = 'https://dentonet.pl/forum-new/./viewtopic.php?f=1&t=45505&sid=381b8b2059634e40b935ecf889620f1d'
link = 'https://dentonet.pl/forum-new/viewtopic.php?f=13&t=16101&sid=d07994463cd2fb283a126da15fcd3ace'
link = 'https://dentonet.pl/forum-new/./viewtopic.php?f=13&t=16101&sid=7e21eeb117ec3beee28e8ac4233ff846'
check_link_in_collection(link, db['DLA WSZYSTKICH'])
# %%
x = db['DLA WSZYSTKICH'].find_one()
print(x)
# %%
print(x)

# %%
for collection in db.list_collection_names():
    print(collection)
    x = db[collection].find_one()
    # write x to o 'test.txt' file 
    with open('test.txt', 'a') as f:
        f.write(collection + '\n' + '\n')
        f.write(str(x))
# %%

link = 'https://dentonet.pl/forum-new/./viewtopic.php?f=13&t=16101&sid=7e21eeb117ec3beee28e8ac4233ff846'
print(remove_sid_from_link(link))
# %%
