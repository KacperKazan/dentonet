from flask import Flask, render_template, request, url_for
from pymongo import MongoClient
import pymongo
import math
from flask_paginate import Pagination, get_page_parameter
from collections import defaultdict

# import ObjectId from bson.objectid
from bson.objectid import ObjectId

# Initialize pagination
THREADS_PER_FORUM_PAGE = 50
POSTS_PER_THREAD_PAGE = 10


app = Flask(__name__)

# Connect to your MongoDB database
client = MongoClient()
db = client['forums']

collection_to_section = {
    'Dla wszystkich': 'DLA WSZYSTKICH',
    'Pomoc techniczna': 'DLA WSZYSTKICH',

    'Forum ogólnostomatologiczne': 'DLA DENTYSTÓW',
    'Forum specjalistyczne': 'DLA DENTYSTÓW',
    'Sprzęt i materiały': 'DLA DENTYSTÓW',
    'Z praktyki wzięte  przypadki': 'DLA DENTYSTÓW',
    'NFZ': 'DLA DENTYSTÓW',
    'Ankiety': 'DLA DENTYSTÓW',
    'Po godzinach': 'DLA DENTYSTÓW',
    
    'Forum specjalistyczne': 'DLA TECHNIKÓW DENTYSTYCZNYCH',
    'Po godzinach': 'DLA TECHNIKÓW DENTYSTYCZNYCH',
    
    'Dla asystentek i higienistek': 'DLA ASYSTENTEK',
    
    'Dla studentów': 'DLA STUDENTÓW',

    'Sprawy forum': 'DLA MODERATORÓW',
}

# Define the routes for your website
@app.route('/')
def main():
    # Query the database for all collection names
    collections = db.list_collection_names()
    # dict with default value of []
    sections = defaultdict(list)
    for collection in collections:
        # find one thread
        threads = db[collection].find({})
        section = collection_to_section[collection]
        dict = {'collection_name': collection, 'num_threads': threads.count()}
        sections[section].append(dict)

    # Render the main.html template with the collection names
    return render_template('main.html', sections=sections)

@app.route('/forum/<collection_name>')
def forum(collection_name):
    # Query the database for all thread objects in the selected collection

    # Separate out the announcement threads from the regular topics
    announcements = db[collection_name].find({'announcement': True})

    # topics where announcement = false
    topics = db[collection_name].find({'announcement': False})
    len_topics = topics.count()
    # count number of topics
    # len_topics = 
    # for thread in threads:
    #     if thread['announcement']:
    #         announcements.append(thread)
    #     else:
    #         topics.append(thread)

    # Paginate the topics
    page = request.args.get(get_page_parameter(), type=int, default=1)
    topics_pagination = Pagination(page=page, per_page=THREADS_PER_FORUM_PAGE, total=len_topics, css_framework='bootstrap4')
    # get next page number

    total_pages = math.ceil(len_topics / THREADS_PER_FORUM_PAGE)
    next_page = min(page + 1, total_pages)
    prev_page = max(page - 1, 1)

    # Get the current page of topics
    start = (page - 1) * THREADS_PER_FORUM_PAGE
    end = start + THREADS_PER_FORUM_PAGE
    topics_page = topics[start:end]

    # Render the forum.html template with the thread objects
    return render_template('forum.html', collection_name=collection_name, announcements=announcements, topics=topics_page, topics_pagination=topics_pagination, num_pages=total_pages, next_page=next_page, prev_page=prev_page)

def parse_html(html):
    # replace &lt; with <
    html =  html.replace('&lt;', '<')
    # replace &gt; with >
    html =  html.replace('&gt;', '>')
    return html

def parse_and_mark_html(x, mark):
    x = parse_html(x)
    if mark and  mark in x:
        x = x.replace(mark, f'<mark>{mark}</mark>')

    return x


@app.route('/thread/<collection_name>/<thread_id>')
@app.route('/thread/<collection_name>/<thread_id>/<int:page>')
@app.route('/thread/<collection_name>/<thread_id>/<int:page>/<mark>')
def thread(collection_name, thread_id, page=1, mark=''):
    # Query the database for the selected thread object and all posts in the thread
    thread = db[collection_name].find_one({'_id': ObjectId(thread_id)})
    posts = thread['posts']

    # Calculate the number of pages based on the number of posts and the posts per page
    num_pages = int(math.ceil(len(posts) / POSTS_PER_THREAD_PAGE))

    # Paginate the posts based on the current page
    start_idx = (page - 1) * POSTS_PER_THREAD_PAGE
    end_idx = start_idx + POSTS_PER_THREAD_PAGE
    paginated_posts = posts[start_idx:end_idx]

    # Generate the pagination links
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < num_pages else None
    pages = []

    for i in range(1, num_pages + 1):
        if i == page:
            pages.append({'num': i, 'url': None})
        else:
            pages.append({'num': i, 'url': url_for('thread', collection_name=collection_name, thread_id=thread_id, page=i)})


    # Render the thread.html template with the thread object, posts, and pagination variables
    return render_template('thread.html', collection_name=collection_name, thread=thread, posts=paginated_posts, prev_page=prev_page, next_page=next_page, pages=pages, num_pages=num_pages, current_page=page, parse_html=parse_and_mark_html, mark=mark)

@app.route('/search', methods=['GET', 'POST'])
def search():
    # Get the search query from the form
    # search_query = request.form['search_query']
    search_query = str(request.args.get('search_query'))

    unique_threads = set()
    #  dictionary with default value of []
    all_results = defaultdict(list)
    # loop through all collections in the database
    for collection_name in db.list_collection_names():
        # get the collection
        collection = db[collection_name]
        # search for the text in the posts content attribute
        results = collection.find({"posts.content": {"$regex": search_query}})
        # iterate over the results
        for result in results:
            # check if the result is already in the set
            if result['_id'] not in unique_threads:
                # if not, add it to the set
                unique_threads.add(result['_id'])
                # get the index of the matching post
                for i, post in enumerate(result["posts"]):
                    if search_query in post["content"]:
                        html = parse_html(post['html'])
                        # surround the search query with <mark> tags in html
                        html = html.replace(search_query, f'<mark>{search_query}</mark>')
                        
                        thread_page_index = math.ceil((i + 1) / POSTS_PER_THREAD_PAGE)

                        thread_page_link = url_for('thread', collection_name=collection_name, thread_id=result['_id'], page=thread_page_index, mark=search_query)

                        search_result = {'thread_id': result['_id'], 'thread_title': result['title'], 'html': html, 'thread_link': thread_page_link}
                        all_results[collection_name].append(search_result)

    # Render the search.html template with the search results
    total_results = sum(len(results) for results in all_results.values())
    return render_template('search.html', search_query=search_query, all_results=all_results, total_results=total_results)

if __name__ == '__main__':
    app.run(debug=True)
