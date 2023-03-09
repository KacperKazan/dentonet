from flask import Flask, render_template, request
from pymongo import MongoClient
import pymongo
import math
from flask_paginate import Pagination, get_page_parameter
# import ObjectId from bson.objectid
from bson.objectid import ObjectId

# Initialize pagination
per_page = 50


app = Flask(__name__)

# Connect to your MongoDB database
client = MongoClient()
db = client['forums']

# Define the routes for your website
@app.route('/')
def main():
    # Query the database for all collection names
    collections = db.list_collection_names()
    print(collections)

    # Render the main.html template with the collection names
    return render_template('main.html', collections=collections)

@app.route('/forum/<collection_name>')
def forum(collection_name):
    # Query the database for all thread objects in the selected collection
    threads = db[collection_name].find()

    # Separate out the announcement threads from the regular topics
    announcements = []
    topics = []
    for thread in threads:
        if thread['announcement']:
            announcements.append(thread)
        else:
            topics.append(thread)

    # Paginate the topics
    page = request.args.get(get_page_parameter(), type=int, default=1)
    topics_pagination = Pagination(page=page, per_page=50, total=len(topics), css_framework='bootstrap4')
    # get next page number

    total_pages = math.ceil(len(topics) / 50)
    next_page = min(page + 1, total_pages)
    prev_page = max(page - 1, 1)

    # Get the current page of topics
    start = (page - 1) * 50
    end = start + 50
    topics_page = topics[start:end]

    # Render the forum.html template with the thread objects
    return render_template('forum.html', collection_name=collection_name, announcements=announcements, topics=topics_page, topics_pagination=topics_pagination, num_pages=total_pages, next_page=next_page, prev_page=prev_page)

def parse_html(html):
    # replace &lt; with <
    html =  html.replace('&lt;', '<')
    # replace &gt; with >
    html =  html.replace('&gt;', '>')
    return html


@app.route('/thread/<collection_name>/<thread_id>')
def thread(collection_name, thread_id):
    # Query the database for the selected thread object and all posts in the thread
    thread = db[collection_name].find_one({'_id': ObjectId(thread_id)})
    posts = thread['posts']

    # Calculate the number of pages based on the number of posts and the posts per page
    posts_per_page = 10
    num_pages = int(math.ceil(len(posts) / posts_per_page))

    # Render the thread.html template with the thread object, posts, and pagination variables
    return render_template('thread.html', collection_name=collection_name, thread=thread, posts=posts, num_pages=num_pages, parse_html=parse_html)


@app.route('/search', methods=['GET', 'POST'])
def search():
    # If the user submits a search query
    if request.method == 'POST':
        # Get the search query from the form
        search_query = request.form['search_query']

        # Use MongoDB's text search functionality to search for matches in the posts collection
        search_results = db.posts.find({'$text': {'$search': search_query}})

        # Render the search.html template with the search results
        return render_template('search.html', search_query=search_query, search_results=search_results)

    # If the user visits the search page without submitting a search query
    else:
        return render_template('search.html')

if __name__ == '__main__':
    app.run(debug=True)
