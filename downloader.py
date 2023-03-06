# %%
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
# %%

class MainSection:
    def __init__(self, header_text, header_link, forums):
        self.header_text = header_text
        self.header_link = header_link
        self.forums = forums
    
    def __str__(self):
        # return header_text, link followed by tab indented list of forums
        return self.header_text  + '\n' + self.header_link + '\n' + '\t' + '\n\t'.join(str(forum) for forum in self.forums)

    

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

class Post:
    def __init__(self, title, link, author, date):
        self.title = title
        self.link = link
        self.author = author
        self.date = date
    
    def __str__(self):
        # title followed by link on separate line
        return self.title + '\n' + self.link + '\n' + self.author + '\n' + str(self.date)
    
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
print(main_sections[0])
# %%
print(main_sections[1])
# %%
def get_topic_posts(url, is_announcement=False):
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

            topic_posts = []
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

                date_time = None
                for child in meta.children:
                    if '»' in child.text:
                        text  = child.text.strip().replace('»', '')
                        # trim text after '\n'
                        text = text.split('\n')[0].strip()
                        for month_name, month_number in polish_months.items():
                            text = text.replace(month_name, str(month_number))
                        
                        format = "%d %m %Y, %H:%M"
                        date_time = datetime.strptime(text, format)
                
                post = Post(topic_name, topic_link, username, date_time)

                topic_posts.append(post)

            return topic_posts

# %%
forum = main_sections[0].forums[0]
# %%
topic_posts = get_topic_posts(forum.link)
print(len(topic_posts))
print('announcements')
for topic_post in topic_posts:
    print('\n\n')
    print(topic_post)
# %%
print(len(topic_posts))
# %%
announcements = get_topic_posts(forum.link, is_announcement=True)
for announcement in announcements:
    print('\n\n')
    print(announcement)
# %%
print(forum.link)
# %%
def is_last_forum_page(url):
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

def get_all_forum_posts(forum):
    i = 640

    keep_going = True
    all_topic_posts = []
    while keep_going:
        url  = forum.get_page_link_at_index(i)
        
        topic_posts  = get_topic_posts(url)
        
        all_topic_posts.extend(topic_posts)

        i += 1
        if is_last_forum_page(url):
            keep_going = False
    return all_topic_posts

posts = get_all_forum_posts(forum)
print(len(posts))
# %%
print(posts[1])
# %%
