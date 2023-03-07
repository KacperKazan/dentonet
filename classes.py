import requests
from bs4 import BeautifulSoup
from datetime import datetime
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
    response = requests.get(url)
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
    
    def __str__(self):
        # return header_text, link followed by tab indented list of forums
        return self.header_text  + '\n' + self.header_link + '\n' + '\t' + '\n\t'.join(str(forum) for forum in self.forums)

class User:
    def __init__(self, username):
        self.username = username

    def __str__(self):
        return self.username
    

class Forum:
    def __init__(self, title, link):
        self.title = title
        self.link = link
        self.increment = 25

    def get_page_link_at_index(self, idx):
        return self.link + f'&start={idx * self.increment}'
    
    def __str__(self):
        # title followed by link on separate line
        return self.title + '\n' + self.link

    def get_topic_announcements(self):
        return self.get_topic_threads(self.link, is_announcement=True)

    def get_topic_threads(self, url, is_announcement=False):
        # Send a request to the URL and get the HTML response
        response = requests.get(url)
        html_content = response.content

        # Use BeautifulSoup to parse the HTML content
        soup = BeautifulSoup(html_content, "html.parser")

        forumbg_string  = 'forumbg announcement' if is_announcement else 'forumbg'
        forabgs = soup.find_all('div', {'class': forumbg_string})
        main_sections = []

        # Loop through each div element with class "forabg"
        for forabg in forabgs:
            # Find all a elements with class "forumtitle"
            forumtitles = forabg.find_all('a', {'class': 'topictitle'})
            topics_table = forabg.find('ul', {'class': 'topiclist topics'})
            topics = topics_table.find_all('li', {'class': 'row'})

            header = forabg.find('div', {'class': 'list-inner'})

            if header:
                header_text = header.text.strip()

                topic_threads = []
                # Loop through each a element with class "forumtitle"
                
                for topic in topics:
                    topic_title = topic.find('a', {'class': 'topictitle'})
                    topic_name = topic_title.text
                    topic_link = base_url + topic_title['href']

                    meta = topic.find('div', {'class': 'responsive-hide'})

                    username = meta.find('a', {'class': 'username'})
                    if not username:
                        username = meta.find('span', {'class': 'username'})
                    username = username.text
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
                    
                    thread = Thread(topic_name, topic_link, user, date_time)

                    topic_threads.append(thread)

                return topic_threads


    def get_all_forum_threads(self):
        i = 650

        keep_going = True
        all_topic_threads = []
        while keep_going:
            url  = self.get_page_link_at_index(i)
            
            topic_threads  = self.get_topic_threads(url)
            
            all_topic_threads.extend(topic_threads)

            i += 1
            if is_last_page(url):
                keep_going = False
        return all_topic_threads


class Post:
    def __init__(self, postcontent):
        # 'content' class and extract the text
        # get the 'author' class and extract the text
        content = postcontent.find('div', {'class': 'content'})
        if content:
            content = content.text.strip()
        else:
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
        
    def __str__(self):
        return self.author.username + '\n' + str(self.datetime) + '\n' + self.content
    

class Thread:
    def __init__(self, title, link, author, date):
        self.title = title
        self.link = link
        self.author = author
        self.date = date
        self.increment = 15


    def get_page_link_at_index(self, idx):
        return self.link + f'&start={idx * self.increment}'
    
    def __str__(self):
        # title followed by link on separate line
        return self.title + '\n' + self.link + '\n' + self.author + '\n' + str(self.date)

    def _get_thread_posts(self, url):
        # get all 'post' class from thread.link
        # loop through each post and parse it with parse_post()
        # return list of parsed posts
        response = requests.get(self.link)
        html_content = response.content

        # Use BeautifulSoup to parse the HTML content
        soup = BeautifulSoup(html_content, "html.parser")

        posts = soup.find_all('div', {'class': 'post'})
        parsed_posts = []
        for post in posts:
            print(url)
            parsed_post = Post(post)
            parsed_posts.append(parsed_post)
        return parsed_posts

    def get_all_thread_posts(self):
        idx = 0
        keep_going = True
        posts = []
        while keep_going:
            url = self.get_page_link_at_index(idx)
            thread_posts = self._get_thread_posts(url)
            posts.extend(thread_posts)
            idx += 1
            if is_last_page(url):
                keep_going = False

        return posts